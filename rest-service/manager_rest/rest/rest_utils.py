import re
import unicodedata

from contextlib import contextmanager
from dateutil import rrule
from datetime import datetime
from string import ascii_letters
import copy
import dateutil.parser
import os
import pytz
import string
import uuid

from retrying import retry
from flask_security import current_user
from flask import request, make_response, current_app
from flask_restful.reqparse import Argument, RequestParser

from dsl_parser import tasks
from dsl_parser import exceptions as parser_exceptions
from dsl_parser.functions import is_function
from dsl_parser.constants import INTER_DEPLOYMENT_FUNCTIONS

from cloudify._compat import urlquote, text_type
from cloudify.snapshots import SNAPSHOT_RESTORE_FLAG_FILE
from cloudify.models_states import (
    VisibilityState,
    BlueprintUploadState,
    ExecutionState,
)

from manager_rest.storage import db, models, user_datastore
from manager_rest.execution_token import current_execution
from manager_rest.constants import RESERVED_LABELS, RESERVED_PREFIX
from manager_rest.dsl_functions import (get_secret_method,
                                        evaluate_intrinsic_functions)
from manager_rest import manager_exceptions, config, app_context
from manager_rest.utils import (parse_recurrence,
                                is_administrator,
                                get_formatted_timestamp)


states_except_private = copy.deepcopy(VisibilityState.STATES)
states_except_private.remove('private')
VISIBILITY_EXCEPT_PRIVATE = states_except_private


class BadLabelsList(manager_exceptions.BadParametersError):
    def __init__(self):
        super().__init__(
            'Labels must be a list of 1-entry dictionaries: '
            '[{<key1>: <value1>}, {<key2>: [<value2>, <value3>]}, ...]')


@contextmanager
def skip_nested_marshalling():
    request.__skip_marshalling = True
    yield
    delattr(request, '__skip_marshalling')


def get_json_and_verify_params(params=None):
    params = params or []
    if request.content_type != 'application/json':
        raise manager_exceptions.UnsupportedContentTypeError(
            'Content type must be application/json')

    request_dict = request.json
    is_params_dict = isinstance(params, dict)

    def is_optional(param_name):
        return is_params_dict and params[param_name].get('optional', False)

    def check_type(param_name):
        return is_params_dict and params[param_name].get('type', None)

    for param in params:
        if param not in request_dict:
            if is_optional(param):
                continue
            raise manager_exceptions.BadParametersError(
                'Missing {0} in json request body'.format(param))

        param_type = check_type(param)
        if param_type and not isinstance(request_dict[param], param_type):
            raise manager_exceptions.BadParametersError(
                '{0} parameter is expected to be of type {1} but is of type '
                '{2}'.format(param,
                             param_type.__name__,
                             type(request_dict[param]).__name__))

        if is_params_dict:
            _validate_allowed_substitutions(
                param_name=param,
                param_value=request_dict[param],
                allowed=params[param].get('allowed_substitutions', None),
            )
    return request_dict


def _validate_allowed_substitutions(param_name, param_value, allowed):
    if allowed is None or param_value is None:
        current_app.logger.debug(
            'Empty value or no allowed substitutions '
            'defined for %s, skipping.', param_name)
        return
    f = string.Formatter()
    invalid = []
    current_app.logger.debug('Checking allowed substitutions for %s (%s)',
                             param_name, ','.join(allowed))
    current_app.logger.debug('Value is: %s', param_value)
    for _, field, _, _ in f.parse(param_value):
        if field is None:
            # This will occur at the end of a string unless the string ends at
            # the end of a field
            continue
        current_app.logger.debug('Found %s', field)
        if field not in allowed:
            current_app.logger.debug('Field not valid.')
            invalid.append(field)
    if invalid:
        raise manager_exceptions.BadParametersError(
            '{candidate_name} has invalid parameters.\n'
            'Invalid parameters found: {invalid}.\n'
            'Allowed: {allowed}'.format(
                candidate_name=param_name,
                invalid=', '.join(invalid),
                allowed=', '.join(allowed),
            )
        )


def get_args_and_verify_arguments(arguments):
    request_parser = RequestParser()
    for argument in arguments:
        argument.location = 'args'
        request_parser.args.append(argument)
    return request_parser.parse_args()


def verify_and_convert_bool(attribute_name, str_bool):
    if isinstance(str_bool, bool):
        return str_bool
    if isinstance(str_bool, text_type):
        if str_bool.lower() == 'true':
            return True
        if str_bool.lower() == 'false':
            return False
    raise manager_exceptions.BadParametersError(
        '{0} must be <true/false>, got {1}'.format(attribute_name, str_bool))


def convert_to_int(value):
    try:
        return int(value)
    except Exception:
        raise manager_exceptions.BadParametersError(
            'invalid parameter, should be int, got: {0}'.format(value))


def make_streaming_response(res_id, res_path, archive_type):
    response = make_response()
    response.headers['Content-Description'] = 'File Transfer'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Content-Type'] = 'application/octet-stream'
    response.headers['Content-Disposition'] = \
        'attachment; filename={0}.{1}'.format(res_id, archive_type)
    response.headers['X-Accel-Redirect'] = res_path
    response.headers['X-Accel-Buffering'] = 'yes'
    return response


def validate_inputs(input_dict, len_input_value=256, err_prefix=None,
                    validate_value_begins_with_letter=True):
    for input_name, input_value in input_dict.items():
        prefix = err_prefix or 'The `{0}` argument'.format(input_name)

        if not input_value:
            raise manager_exceptions.BadParametersError(
                '{0} is empty'.format(prefix)
            )

        if len(input_value) > len_input_value:
            raise manager_exceptions.BadParametersError(
                '{0} is too long. Maximum allowed length is {1} '
                'characters'.format(prefix, len_input_value)
            )

        # urllib.quote changes all chars except alphanumeric chars and _-.
        quoted_value = urlquote(input_value, safe='')
        if quoted_value != input_value:
            raise manager_exceptions.BadParametersError(
                '{0} contains illegal characters. Only letters, digits and the'
                ' characters "-", "." and "_" are allowed'.format(prefix)
            )

        if validate_value_begins_with_letter and \
                input_value[0] not in ascii_letters:
            raise manager_exceptions.BadParametersError(
                '{0} must begin with a letter'.format(prefix)
            )


def validate_and_decode_password(password):
    if not password:
        raise manager_exceptions.BadParametersError('The password is empty')

    if len(password) > 256:
        raise manager_exceptions.BadParametersError(
            'The password is too long. Maximum allowed length is 256 '
            'characters'
        )

    if len(password) < 5:
        raise manager_exceptions.BadParametersError(
            'The password is too short. Minimum allowed length is 5 '
            'characters'
        )

    return password


def verify_role(role_name, is_system_role=False):
    """Make sure that role name is present in the system.

    :param role_name: Role name to validate against database content.
    :param is_system_role: True if system_role, False if tenant_role
    :raises: BadParametersError when role is not found in the system or is
    not from the right type

    """
    expected_role_type = 'system_role' if is_system_role else 'tenant_role'

    # Get role by name
    role = next(
        (
            r
            for r in config.instance.authorization_roles
            if r['name'] == role_name
        ),
        None
    )

    # Role not found
    if role is None:
        valid_roles = [
            r['name']
            for r in config.instance.authorization_roles
            if r['type'] in (expected_role_type, 'any')
        ]
        raise manager_exceptions.BadParametersError(
            'Invalid role: `{0}`. Valid {1} roles are: {2}'
            .format(role_name, expected_role_type, valid_roles)
        )

    # Role type doesn't match
    if role['type'] not in (expected_role_type, 'any'):
        raise manager_exceptions.BadParametersError(
            'Role `{0}` is a {1} and cannot be assigned as a {2}'
            .format(role_name, role['type'], expected_role_type)
        )


def request_use_all_tenants():
    return verify_and_convert_bool('all_tenants',
                                   request.args.get('_all_tenants', False))


def get_visibility_parameter(optional=False,
                             is_argument=False,
                             valid_values=VISIBILITY_EXCEPT_PRIVATE):
    if is_argument:
        args = get_args_and_verify_arguments(
            [Argument('visibility', default=None)]
        )
        visibility = args.visibility
    else:
        request_dict = get_json_and_verify_params({
            'visibility': {'optional': optional, 'type': text_type}
        })
        visibility = request_dict.get('visibility', None)

    if visibility is not None and visibility not in valid_values:
        raise manager_exceptions.BadParametersError(
            "Invalid visibility: `{0}`. Valid visibility's values are: {1}"
            .format(visibility, valid_values)
        )
    return visibility


def parse_datetime_string(datetime_str):
    """
    :param datetime_str: A string representing date and time with timezone
                         information.
    :return: A datetime object, converted to UTC, with no timezone info.
    """
    # Parse the string to datetime object
    date_with_offset = dateutil.parser.parse(datetime_str)

    # Convert the date to UTC
    try:
        utc_date = date_with_offset.astimezone(pytz.utc)
    except ValueError:
        raise manager_exceptions.BadParametersError(
            'Date `{0}` missing timezone information, please provide'
            ' valid date. \nExpected format: YYYYMMDDHHMM+HHMM or'
            ' YYYYMMDDHHMM-HHMM i.e: 201801012230-0500'
            ' (Jan-01-18 10:30pm EST)'.format(datetime_str))

    # Date is in UTC, tzinfo is not necessary
    return utc_date.replace(tzinfo=None)


def is_hidden_value_permitted(secret):
    return is_administrator(secret.tenant) or \
        secret.created_by == current_user.username


def is_system_in_snapshot_restore_process():
    return os.path.exists(SNAPSHOT_RESTORE_FLAG_FILE)


def get_parsed_deployment(blueprint,
                          app_dir,
                          app_blueprint):
    file_server_root = config.instance.file_server_root
    blueprint_resource_dir = os.path.join(file_server_root,
                                          'blueprints',
                                          blueprint.tenant_name,
                                          blueprint.id)
    # The dsl parser expects a URL
    blueprint_resource_dir_url = 'file:{0}'.format(blueprint_resource_dir)
    app_path = os.path.join(file_server_root, app_dir, app_blueprint)

    try:
        return tasks.parse_dsl(
            app_path,
            resources_base_path=file_server_root,
            additional_resources=[blueprint_resource_dir_url],
            **app_context.get_parser_context()
        )
    except parser_exceptions.DSLParsingException as ex:
        raise manager_exceptions.InvalidBlueprintError(
            'Invalid blueprint - {0}'.format(ex))


def get_deployment_plan(parsed_deployment,
                        inputs,
                        runtime_only_evaluation=False,
                        auto_correct_types=False):
    try:
        return tasks.prepare_deployment_plan(
            parsed_deployment, get_secret_method, inputs=inputs,
            runtime_only_evaluation=runtime_only_evaluation,
            auto_correct_types=auto_correct_types)
    except parser_exceptions.MissingRequiredInputError as e:
        raise manager_exceptions.MissingRequiredDeploymentInputError(
            str(e))
    except parser_exceptions.UnknownInputError as e:
        raise manager_exceptions.UnknownDeploymentInputError(str(e))
    except parser_exceptions.UnknownSecretError as e:
        raise manager_exceptions.UnknownDeploymentSecretError(str(e))
    except parser_exceptions.UnsupportedGetSecretError as e:
        raise manager_exceptions.UnsupportedDeploymentGetSecretError(
            str(e))


def update_deployment_dependencies_from_plan(deployment_id,
                                             deployment_plan,
                                             storage_manager,
                                             dep_plan_filter_func,
                                             curr_dependencies=None):
    curr_dependencies = {} if curr_dependencies is None else curr_dependencies

    new_dependencies = deployment_plan.setdefault(
        INTER_DEPLOYMENT_FUNCTIONS, {})
    new_dependencies_dict = {
        creator: (target[0], target[1])
        for creator, target in new_dependencies.items()
        if dep_plan_filter_func(creator)
    }
    source_deployment = storage_manager.get(models.Deployment,
                                            deployment_id,
                                            all_tenants=True)
    dependents = source_deployment.get_all_dependents()
    for dependency_creator, target_deployment_attr \
            in new_dependencies_dict.items():
        target_deployment_id = target_deployment_attr[0]
        target_deployment_func = target_deployment_attr[1]
        target_deployment = storage_manager.get(
            models.Deployment, target_deployment_id, all_tenants=True) \
            if target_deployment_id else None

        if dependency_creator not in curr_dependencies:
            now = get_formatted_timestamp()
            storage_manager.put(models.InterDeploymentDependencies(
                dependency_creator=dependency_creator,
                source_deployment=source_deployment,
                target_deployment=target_deployment,
                target_deployment_func=target_deployment_func,
                created_at=now,
                id=str(uuid.uuid4())
            ))
            continue

        curr_target_deployment = \
            curr_dependencies[dependency_creator].target_deployment
        if curr_target_deployment == target_deployment_id:
            continue

        curr_dependencies[dependency_creator].target_deployment = \
            target_deployment
        curr_dependencies[dependency_creator].target_deployment_func = \
            target_deployment_func
        storage_manager.update(curr_dependencies[dependency_creator])
        # verify that the new dependency doesn't create a cycle,
        # and update the dependencies graph accordingly
        if ((not hasattr(source_deployment, 'id')) or (not target_deployment)
                or not hasattr(curr_target_deployment, 'id')):
            continue
            # upcoming: handle the case of external dependencies
        if target_deployment._storage_id in dependents:
            raise manager_exceptions.ConflictError(
                f'cyclic dependency between {source_deployment.id} '
                f'and {target_deployment.id}')
    return new_dependencies_dict


def update_inter_deployment_dependencies(sm, deployment):
    dependencies_list = (
        db.session.query(models.InterDeploymentDependencies)
        .filter(
            models.InterDeploymentDependencies._source_deployment
            == deployment._storage_id
        )
        .all()
    )
    if not dependencies_list:
        return
    components_list = [
        dep.target_deployment for dep in dependencies_list
        if dep.dependency_creator.startswith('component.')
    ]
    shared_resources_list = [
        dep.target_deployment for dep in dependencies_list
        if dep.dependency_creator.startswith('sharedresource.')
        and not dep.external_target
    ]
    dependencies_list = [
        dep for dep in dependencies_list
        if dep.target_deployment_func and not dep.external_target
    ]
    consumer_labels_to_add = set()
    dependents = {
        d._source_deployment
        for d in deployment.get_dependents(fetch_deployments=False)
    } | {deployment._storage_id}

    for dependency in dependencies_list:
        eval_target_deployment = _get_deployment_from_target_func(
            sm,
            dependency.target_deployment_func,
            dependency.source_deployment_id
        )

        if not eval_target_deployment or \
                eval_target_deployment == dependency.target_deployment:
            continue

        if eval_target_deployment._storage_id in dependents:
            raise manager_exceptions.ConflictError(
                f'Cyclic dependency between {deployment} '
                f'and {eval_target_deployment}'
            )
        dependency.target_deployment = eval_target_deployment
        sm.update(dependency)

        # Add source to target's consumers (except where target is a component)
        if dependency.target_deployment in components_list:
            continue
        consumer_labels_to_add.add((dependency.source_deployment_id,
                                    eval_target_deployment))

    # Add consumer labels for shared resources
    for shared_resource in shared_resources_list:
        consumer_labels_to_add.add((deployment.id, shared_resource))

    _add_new_consumer_labels(sm, consumer_labels_to_add)


def _add_new_consumer_labels(sm, consumer_labels_to_add):
    existing_consumer_labels = {
        (lb.value, lb.deployment) for lb in
        sm.list(models.DeploymentLabel, filters={'key': 'csys-consumer-id'})
    }
    consumer_labels_to_add -= existing_consumer_labels
    for label in consumer_labels_to_add:
        source_id, target = label
        sm.put(models.DeploymentLabel(
            key='csys-consumer-id',
            value=source_id,
            created_at=datetime.utcnow(),
            creator=current_user,
            deployment=target,
        ))


def _evaluate_target_func(target_dep_func, source_dep_id):
    if is_function(target_dep_func):
        evaluated_func = evaluate_intrinsic_functions(
            {'target_deployment': target_dep_func}, source_dep_id)
        return evaluated_func.get('target_deployment')

    return target_dep_func


def _get_deployment_from_target_func(sm, target_dep_func, source_dep_id):
    target_dep_id = _evaluate_target_func(target_dep_func, source_dep_id)
    if target_dep_id:
        return sm.get(models.Deployment, target_dep_id, fail_silently=True,
                      all_tenants=True)

    return None


def verify_blueprint_uploaded_state(blueprint):
    if blueprint.state in BlueprintUploadState.FAILED_STATES:
        raise manager_exceptions.InvalidBlueprintError(
            'Required blueprint `{}` has failed to upload. State: {}, '
            'Error: {}'.format(blueprint.id, blueprint.state, blueprint.error))
    if blueprint.state and blueprint.state != BlueprintUploadState.UPLOADED:
        raise manager_exceptions.InvalidBlueprintError(
            'Required blueprint `{}` is still {}.'
            .format(blueprint.id, blueprint.state))


def _execution_ended(result):
    return result.status not in ExecutionState.END_STATES


@retry(wait_fixed=1000, stop_max_attempt_number=120,
       retry_on_result=_execution_ended)
def wait_for_execution(sm, execution_id):
    execution = sm.get(models.Execution, execution_id)
    sm._safe_commit()
    return execution


def get_uploaded_blueprint(sm, blueprint):
    wait_for_execution(sm, blueprint.upload_execution.id)
    blueprint = sm.get(models.Blueprint, blueprint.id)
    if blueprint.state in BlueprintUploadState.FAILED_STATES:
        if blueprint.state == BlueprintUploadState.INVALID:
            state_display = 'is invalid'
        else:
            state_display = 'has {}'.format(blueprint.state.replace('_', ' '))
        raise manager_exceptions.InvalidBlueprintError(
            'Blueprint `{}` {}. Error: {}'.format(
                blueprint.id, state_display, blueprint.error))
    return blueprint, 201


def parse_datetime_multiple_formats(date_str):
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S.%fZ'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    raise manager_exceptions.BadParametersError(
        "{} is not a legal time format".format(date_str))


def get_labels_list(raw_labels_list):
    labels_list = []
    for label in raw_labels_list:
        if (not isinstance(label, dict)) or len(label) != 1:
            raise BadLabelsList()

        [(key, raw_value)] = label.items()
        values_list = raw_value if isinstance(raw_value, list) else [raw_value]
        for value in values_list:
            parsed_key, parsed_value = parse_label(key, value)
            labels_list.append((parsed_key, parsed_value))

    test_unique_labels(labels_list)
    return labels_list


def parse_label(label_key, label_value):
    if ((not isinstance(label_key, text_type)) or
            (not isinstance(label_value, text_type))):
        raise BadLabelsList()

    if len(label_key) > 256 or len(label_value) > 256:
        raise manager_exceptions.BadParametersError(
            'The key or value is too long. Maximum allowed length is '
            '256 characters'
        )

    if urlquote(label_key, safe='') != label_key:
        raise manager_exceptions.BadParametersError(
            f'The key `{label_key}` contains illegal characters. '
            f'Only letters, digits and the characters `-`, `.` and '
            f'`_` are allowed'
        )

    if any(unicodedata.category(char)[0] == 'C' or char == '"'
           for char in label_value):
        raise manager_exceptions.BadParametersError(
            f'The value `{label_value}` contains illegal characters. '
            f'Control characters and `"` are not allowed.'
        )

    parsed_label_key = label_key.lower()
    parsed_label_value = normalize_value(label_value)

    if (parsed_label_key.startswith(RESERVED_PREFIX) and
            parsed_label_key not in RESERVED_LABELS):
        allowed_cfy_labels = ', '.join(RESERVED_LABELS)
        raise manager_exceptions.BadParametersError(
            f'All labels with a `{RESERVED_PREFIX}` prefix are reserved for '
            f'internal use. Allowed `{RESERVED_PREFIX}` prefixed labels '
            f'are: {allowed_cfy_labels}')

    return parsed_label_key, parsed_label_value


def get_labels_from_plan(plan, labels_entry):
    plan_labels_dict = plan.get(labels_entry)
    if plan_labels_dict:
        raw_plan_labels_list = [{key: value['values']} for key, value
                                in plan_labels_dict.items()]
        return get_labels_list(raw_plan_labels_list)

    return []


def test_unique_labels(labels_list):
    if len(set(labels_list)) != len(labels_list):
        raise manager_exceptions.BadParametersError(
            'You cannot define the same label twice')


def compute_rule_from_scheduling_params(request_dict, existing_rule=None):
    rrule_string = request_dict.get('rrule')
    recurrence = request_dict.get('recurrence')
    weekdays = request_dict.get('weekdays')
    count = request_dict.get('count')

    # we need to have at least: rrule; or count=1; or recurrence
    if rrule_string:
        if recurrence or weekdays or count:
            raise manager_exceptions.BadParametersError(
                "`rrule` cannot be provided together with `recurrence`, "
                "`weekdays` or `count`.")
        try:
            rrule.rrulestr(rrule_string)
        except ValueError as e:
            raise manager_exceptions.BadParametersError(
                "invalid RRULE string provided: {}".format(e))
        return {'rrule': rrule_string}
    else:
        if count:
            count = convert_to_int(request_dict.get('count'))
        recurrence = _verify_schedule_recurrence(
            request_dict.get('recurrence'))
        weekdays = _verify_weekdays(request_dict.get('weekdays'), recurrence)
        if existing_rule:
            count = count or existing_rule.get('count')
            recurrence = recurrence or existing_rule.get('recurrence')
            weekdays = weekdays or existing_rule.get('weekdays')

        if not recurrence and count != 1:
            raise manager_exceptions.BadParametersError(
                "recurrence must be specified for execution count larger "
                "than 1")
        return {
            'recurrence': recurrence,
            'count': count,
            'weekdays': weekdays
        }


def _verify_schedule_recurrence(recurrence_str):
    if not recurrence_str:
        return
    _, recurrence = parse_recurrence(recurrence_str)
    if not recurrence:
        raise manager_exceptions.BadParametersError(
            "`{}` is not a legal recurrence expression. Supported format "
            "is: <number> seconds|minutes|hours|days|weeks|months|years"
            .format(recurrence_str))
    return recurrence_str


def _verify_weekdays(weekdays, recurrence):
    if not weekdays:
        return
    if not isinstance(weekdays, list):
        raise manager_exceptions.BadParametersError(
            "weekdays: expected a list, but got: {}".format(weekdays))
    weekdays_caps = [d.upper() for d in weekdays]
    valid_weekdays = {str(d) for d in rrule.weekdays}

    complex_weekdays_freq = False
    if recurrence:
        _, recurrence = parse_recurrence(recurrence)
        complex_weekdays_freq = (recurrence in ['mo', 'month', 'y', 'year'])

    for weekday in weekdays_caps:
        parsed = re.findall(r"^([1-4]|L-)?({})".format(
            '|'.join(valid_weekdays)), weekday)
        if not parsed:
            raise manager_exceptions.BadParametersError(
                "weekdays list contains an invalid weekday `{}`. Valid "
                "weekdays are: {} or their lowercase values, optionally "
                "prefixed by 1-4 or l-/L-.".format(weekday,
                                                   '|'.join(valid_weekdays)))
        if parsed[0][0] and not complex_weekdays_freq:
            raise manager_exceptions.BadParametersError(
                "complex weekday expression {} can only be used with a months|"
                "years recurrence, but got {}.".format(weekday, recurrence))
    return weekdays_caps


def deployment_group_id_filter():
    """Format the deployment group_id filter"""
    if '_group_id' in request.args:
        return {
            'deployment_groups': lambda col: col.any(
                models.DeploymentGroup.id == request.args['_group_id'])
        }
    return {}


def dependency_of_filter(sm):
    """Format the deployment group_id filter"""
    if '_dependencies_of' in request.args:
        src_deployment = sm.get(
            models.Deployment, request.args['_dependencies_of'])
        return {'id': [d.id for d in src_deployment.get_dependencies()]}
    return {}


def licensed_environments_filter():
    """Format the deployment group_id filter"""
    if request.args.get('_environments_only'):
        return {
            '_storage_id': lambda col:
                ~models.InterDeploymentDependencies.query.filter(
                    col ==
                    models.InterDeploymentDependencies._target_deployment,
                    models.InterDeploymentDependencies.dependency_creator.like(
                        'component.%')
                ).exists()
        }
    return {}


def normalize_value(value):
    return unicodedata.normalize('NFKC', value)


def is_deployment_update():
    """Is the current request within a deployment-update execution?"""
    return current_execution and current_execution.workflow_id in (
        'update', 'csys_new_deployment_update')


def valid_user(input_value):
    """Convert a user name to a User object, or raise an exception if the user
    does not exist.
    """
    user = user_datastore.get_user(input_value)
    if not user:
        raise manager_exceptions.BadParametersError(
            'User {} does not exist.'.format(input_value))
    return user


def defines_component(sm, dep: models.DeploymentLabelsDependencies) -> bool:
    """Checks if the source deployment defined by deployment dependency `dep`
    is a component created by target deployment of that dependency.
    """
    idds = sm.list(models.InterDeploymentDependencies,
                   filters={'target_deployment': dep.source_deployment,
                            'source_deployment': dep.target_deployment})
    return all(idd.dependency_creator.startswith('component.')
               for idd in idds) if idds else False

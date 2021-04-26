import re
import unicodedata
from collections import defaultdict, deque

from ast import literal_eval
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
    DeploymentState,
)

from manager_rest.storage import db, models
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


def validate_inputs(input_dict, len_input_value=256, err_prefix=None):
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

        if input_value[0] not in ascii_letters:
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
    dep_graph = RecursiveDeploymentDependencies(storage_manager)
    dep_graph.create_dependencies_graph()

    source_deployment = storage_manager.get(models.Deployment,
                                            deployment_id,
                                            all_tenants=True)
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
        source_id = source_deployment.id
        target_id = target_deployment.id
        old_target_id = curr_target_deployment.id
        dep_graph.assert_no_cyclic_dependencies(source_id, target_id)
        if target_deployment not in new_dependencies_dict.values():
            dep_graph.remove_dependency_from_graph(source_id, old_target_id)
        dep_graph.add_dependency_to_graph(source_id, target_id)
    return new_dependencies_dict


class BaseDeploymentDependencies(object):
    cyclic_error_message = None

    def __init__(self, sm):
        self.graph = None
        self.sm = sm

    def add_dependency_to_graph(self, source_deployment, target_deployment):
        self.graph.setdefault(target_deployment, set()).add(source_deployment)

    def remove_dependency_from_graph(self,
                                     source_deployment, target_deployment):
        if target_deployment in self.graph and \
                source_deployment in self.graph[target_deployment]:
            self.graph[target_deployment].remove(source_deployment)
            if not self.graph[target_deployment]:
                del self.graph[target_deployment]

    def assert_cyclic_dependencies_on_graph(self, graph):
        # DFS to find cycles
        v = list(graph)[0]
        recursion_stack = [v]
        while graph:
            while v not in graph.keys():
                recursion_stack.pop()
                if recursion_stack:
                    recursion_stack[-1]
                else:
                    v = list(graph)[0]
                    recursion_stack = [v]
            u = graph[v].pop()
            if not graph[v]:
                del graph[v]
            v = u
            if v in recursion_stack:
                raise manager_exceptions.ConflictError(
                    self.cyclic_error_message
                )
            recursion_stack.append(v)

    def assert_no_cyclic_dependencies(self,
                                      source_deployment, target_deployment):
        graph = copy.deepcopy(self.graph)
        graph.setdefault(target_deployment, set()).add(source_deployment)
        self.assert_cyclic_dependencies_on_graph(graph)

    def _get_inverted_graph(self):
        inverted_graph_graph = {}  # invert dependencies graph
        for key, val in self.graph.items():
            for item in val:
                inverted_graph_graph.setdefault(item, set()).add(key)
        return inverted_graph_graph

    def create_dependencies_graph(self):
        raise NotImplementedError


class RecursiveDeploymentDependencies(BaseDeploymentDependencies):
    cyclic_error_message = 'Deployment creation results' \
                           ' in cyclic inter-deployment dependencies.'

    def create_dependencies_graph(self):
        if self.graph:
            return
        dependencies = self.sm.list(models.InterDeploymentDependencies)
        self.graph = {}
        for dependency in dependencies:
            if not hasattr(dependency, 'source_deployment_id'):
                continue
            if dependency.source_deployment_id:
                source = dependency.source_deployment_id
            else:
                source = 'EXTERNAL::{}'.format(dependency.external_source)
            target = dependency.target_deployment_id
            if target:
                self.add_dependency_to_graph(source, target)

    def find_recursive_components(self, source_id):
        inv_graph = self._get_inverted_graph()
        # BFS to find components
        queue = {source_id}
        results = set()
        while queue:
            v = queue.pop()
            if v not in inv_graph:
                continue
            dependencies = self.sm.list(
                models.InterDeploymentDependencies,
                filters={'source_deployment_id': v})
            for dependency in dependencies:
                if (dependency.target_deployment_id in inv_graph[v] and
                        dependency.dependency_creator.split('.')[0] ==
                        'component'):
                    queue.add(dependency.target_deployment_id)
                    results.add(dependency.target_deployment_id)
        return results

    def retrieve_dependent_deployments(self, target_id):
        # BFS to traverse all deployment IDs accessing the requested one
        target_group = {target_id} | self.find_recursive_components(target_id)
        queue = target_group.copy()
        results = []
        while queue:
            v = queue.pop()
            if v not in self.graph:
                continue
            queue |= self.graph[v]
            for u in self.graph[v]:
                if u in target_group:
                    # don't add the target itself or its component deployments
                    continue
                source_metadata = None
                if u.startswith('EXTERNAL::'):
                    source_metadata = literal_eval(u.split('::')[1])
                    dependencies = self.sm.list(
                        models.InterDeploymentDependencies,
                        filters={'external_source': source_metadata})
                else:
                    dependencies = self.sm.list(
                        models.InterDeploymentDependencies,
                        filters={'source_deployment_id': u})

                for dependency in dependencies:
                    if dependency.target_deployment_id != v:
                        continue
                    dep_creator = dependency.dependency_creator.split('.')
                    dep_type = dep_creator[0] \
                        if dep_creator[0] in ['component', 'sharedresource'] \
                        else 'deployment'
                    dep_node = dep_creator[1]
                    if source_metadata:
                        deployment_name = '{0} on {1}'.format(
                            source_metadata['deployment'],
                            source_metadata['host'])
                        tenant_name = source_metadata['tenant']
                    else:
                        deployment_name = u
                        tenant_name = dependency.tenant_name
                    dependency_data = {
                        'deployment': deployment_name,
                        'dependency_type': dep_type,
                        'dependent_node': dep_node,
                        'tenant': tenant_name
                    }
                    if dependency_data not in results:
                        results.append(dependency_data)
        return results

    def retrieve_and_display_dependencies(self, target_id,
                                          excluded_component_creator_ids=None):
        if excluded_component_creator_ids is None:
            excluded_component_creator_ids = []
        self.create_dependencies_graph()
        dependencies = self.retrieve_dependent_deployments(target_id)
        dependencies = [d for d in dependencies if
                        d['deployment'] not in excluded_component_creator_ids]
        dependency_display = '  [{0}] Deployment `{1}` {2} the current ' \
                             'deployment in its node `{3}`'
        type_display = {'component': 'contains',
                        'sharedresource': 'uses a shared resource from',
                        'deployment': 'uses capabilities of'}
        return '\n'.join(
            [dependency_display.format(i + 1,
                                       d['deployment'],
                                       type_display[d['dependency_type']],
                                       d['dependent_node'])
             for i, d in enumerate(dependencies)])


class RecursiveDeploymentLabelsDependencies(BaseDeploymentDependencies):
    cyclic_error_message = 'Deployments adding labels results in ' \
                           'cyclic deployment-labels dependencies.'

    def create_dependencies_graph(self):
        """
        Create deployment labels dependencies from the
        `DeploymentLabelsDependencies` model where it contains dict for all
        graph
        :return: Deployment labels graph
        :rtype Dict
        """
        if self.graph:
            return
        dependencies = self.sm.list(
            models.DeploymentLabelsDependencies,
            get_all_results=True
        )
        self.graph = {}
        for dependency in dependencies:
            source = dependency.source_deployment_id
            target = dependency.target_deployment_id
            if source and target:
                self.add_dependency_to_graph(source, target)

    def find_recursive_deployments(self, source_ids):
        """
        Find all deployments that are referenced directly and indirectly
        referenced by Deployment id `source_id`
        :param source_ids: List of deployment ids
        :return:List of recursive deployments that are connected by
        `source_ids` deployments
        :rtype List
        """
        inv_graph = self._get_inverted_graph()
        # BFS to find deployments
        _source_ids = source_ids.copy()
        queue = _source_ids
        results = []
        visited = defaultdict(bool)
        while queue:
            v = queue.pop()
            if v not in inv_graph:
                continue
            dependencies = self.sm.list(
                models.DeploymentLabelsDependencies,
                filters={'source_deployment_id': v},
                get_all_results=True
            )

            for dependency in dependencies:
                if dependency.target_deployment_id in inv_graph[v]:
                    if not visited[dependency.target_deployment_id]:
                        queue.append(dependency.target_deployment_id)
                        results.append(dependency.target_deployment_id)
                        visited[dependency.target_deployment_id] = True
        return results

    def increase_deployment_counts_in_graph(self,
                                            target_ids,
                                            total_services,
                                            total_environments):
        """
        Increase the deployment counts for target deployment that is
        referenced directly by the `source` deployment and then make sure to
        propagate that increase to all deployment that are referenced
        directly and indirectly by `target` deployment
        :param target_ids: Target Deployment ID that we need to attach
        source to
        :rtype list
        :param total_services: Total number of services to add
        :rtype int
        :param total_environments: Total number of environments to add
        :rtype int
        """
        target_group = target_ids + self.find_recursive_deployments(target_ids)
        for target_id in target_group:
            if total_services or total_environments:
                target = self.sm.get(
                    models.Deployment,
                    target_id,
                    locking=True,
                    fail_silently=True
                )
                if target:
                    target.sub_services_count += total_services
                    target.sub_environments_count += total_environments
                    self.sm.update(target)
                    db.session.flush()

    def decrease_deployment_counts_in_graph(self,
                                            target_ids,
                                            total_services,
                                            total_environments):
        """
        Decrease the counter for each deployment that is referenced
        directly and indirectly by `source` deployment and the counts that
        need to be update are possibly for `sub_environments_count`
        & `sub_services_count`
        :param target_ids: Target Deployment IDs that we need to de-attach
        source from
        :rtype list
        :param total_services: Total number of services to remove
        :rtype int
        :param total_environments: Total number of environments to remove
        :rtype int
        """
        target_group = target_ids + self.find_recursive_deployments(
            target_ids
        )
        if target_group:
            for target_id in target_group:
                target = self.sm.get(
                    models.Deployment,
                    target_id,
                    locking=True,
                    fail_silently=True
                )
                if target:
                    if target.sub_services_count:
                        target.sub_services_count -= total_services
                    if target.sub_environments_count:
                        target.sub_environments_count -= total_environments
                    self.sm.update(target)
                    db.session.flush()

    def update_deployment_counts_after_source_conversion(self,
                                                         source,
                                                         convert_type):
        """
        Update counter for deployment that is already connected to other
        deployments where deployment could be changed from `service` to
        `environment` and vice versa and we need to take care of deployment
        counters so that count will not mess up
        :param source: Deployment source instance that its type get changed
        :param convert_type: The type we need to convert source deployment
        to. It could be changed from `service` to `environment` and vice versa
        """
        if convert_type not in ('environment', 'service',):
            return
        if convert_type == 'environment':
            env_to_update = 1
            srv_to_update = -1
        else:
            env_to_update = -1
            srv_to_update = 1

        target_group = self.find_recursive_deployments([source.id])
        for target_id in target_group:
            target = self.sm.get(
                models.Deployment,
                target_id,
                locking=True
            )
            target.sub_services_count += srv_to_update
            target.sub_environments_count += env_to_update
            self.sm.update(target)
            db.session.flush()

    def propagate_deployment_statuses(self, source_id):
        """
        Propagate deployment statuses for source deployment to all connected
        in graph that referenced by this node directly and indirectly
        :param source_id: Deployment id
        :rtype str
        """
        def _update_deployment_status(dep, srv_status, env_status):
            _target = self.sm.get(
                models.Deployment,
                dep,
                locking=True,
                fail_silently=True
            )
            if _target:
                _target.sub_environments_status = env_status
                _target.sub_services_status = srv_status
                _target.deployment_status = \
                    _target.evaluate_deployment_status()
                self.sm.update(_target)
                db.session.flush()
        queue = deque([source_id] + self.find_recursive_deployments(
            [source_id]
        ))
        while queue:
            v = queue.popleft()
            if v not in self.graph:
                _update_deployment_status(v, None, None)
                continue
            from_dependencies = self.sm.list(
                models.DeploymentLabelsDependencies,
                filters={'target_deployment_id': v},
                get_all_results=True
            )
            if not from_dependencies:
                continue
            total_env_status = None
            total_srv_status = None
            for from_dependency in from_dependencies:
                if from_dependency.source_deployment_id in self.graph[v]:
                    _source = from_dependency.source_deployment
                    _sub_srv_status, _sub_env_status = \
                        _source.evaluate_sub_deployments_statuses()
                    if _sub_env_status == DeploymentState.REQUIRE_ATTENTION \
                            and _sub_srv_status == \
                            DeploymentState.REQUIRE_ATTENTION:
                        total_env_status = DeploymentState.REQUIRE_ATTENTION
                        total_srv_status = DeploymentState.REQUIRE_ATTENTION
                        break

                    total_env_status = _source.compare_between_statuses(
                        total_env_status, _sub_env_status
                    )
                    total_srv_status = _source.compare_between_statuses(
                        total_srv_status, _sub_srv_status
                    )
            _update_deployment_status(v, total_srv_status, total_env_status)

    def retrieve_and_display_dependencies(self, target):
        self.create_dependencies_graph()
        queue = [target.id]
        visited = defaultdict(bool)
        dependencies = []
        while queue:
            v = queue.pop()
            if v not in self.graph:
                continue
            from_dependencies = self.sm.list(
                models.DeploymentLabelsDependencies,
                filters={'target_deployment_id': v},
                get_all_results=True
            )
            if not from_dependencies:
                continue
            for from_dependency in from_dependencies:
                if from_dependency.source_deployment_id in self.graph[v]:
                    if not visited[from_dependency.source_deployment_id]:
                        queue.append(from_dependency.source_deployment_id)
                        dependencies.append({
                            'parent':
                                from_dependency.target_deployment_id,
                            'child':
                                from_dependency.source_deployment_id
                        })
                        visited[from_dependency.source_deployment_id] = True
        dependency_display = '  [{0}] Deployment `{1}` depends on `{2}`'
        return '\n'.join(
            dependency_display.format(i + 1,
                                      d['child'],
                                      d['parent'])
            for i, d in enumerate(dependencies))

    def assert_cyclic_dependencies_between_targets_and_source(self,
                                                              targets,
                                                              source):
        if targets and source:
            graph = copy.deepcopy(self.graph)
            for target in targets:
                graph.setdefault(target, set()).add(source)
            self.assert_cyclic_dependencies_on_graph(graph)


def update_inter_deployment_dependencies(sm):
    dependencies_list = sm.list(models.InterDeploymentDependencies)
    for dependency in dependencies_list:
        if (dependency.target_deployment_func and
                not dependency.external_target):
            _update_dependency_target_deployment(sm, dependency)


def _update_dependency_target_deployment(sm, dependency):
    eval_target_deployment = _get_deployment_from_target_func(
        sm, dependency.target_deployment_func, dependency.source_deployment_id)
    if (eval_target_deployment and
            eval_target_deployment != dependency.target_deployment):
        dependency.target_deployment = eval_target_deployment

        # check for cyclic dependencies
        dep_graph = RecursiveDeploymentDependencies(sm)
        source_id = str(dependency.source_deployment_id)
        target_id = str(eval_target_deployment.id)
        dep_graph.create_dependencies_graph()
        dep_graph.assert_no_cyclic_dependencies(source_id, target_id)

        sm.update(dependency)


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


@retry(wait_fixed=1000, stop_max_attempt_number=60,
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
    parsed_label_value = unicodedata.normalize('NFKC', label_value)

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


def modify_blueprints_list_args(filters, _include):
    """
    As blueprints list can be retrieved both using `POST /searches/blueprints`
    and `GET /blueprints`, we need a function to serve both endpoints to modify
    the `filters` and `_include` arguments.
    """
    if _include and 'labels' in _include:
        _include = None
    if filters is None:
        filters = {}
    filters.setdefault('is_hidden', False)
    return filters, _include


def modify_deployments_list_args(filters, _include):
    """
    As blueprints list can be retrieved both using `POST /searches/blueprints`
    and `GET /blueprints`, we need a function to serve both endpoints to modify
    the `filters` and `_include` arguments.
    """
    if '_group_id' in request.args:
        filters['deployment_groups'] = lambda col: col.any(
            models.DeploymentGroup.id == request.args['_group_id']
        )
    if _include:
        if {'labels', 'deployment_groups'}.intersection(_include):
            _include = None

    return filters, _include

#########
# Copyright (c) 2015-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import os
import uuid
import pytz
import copy
import subprocess
import dateutil.parser
from ast import literal_eval
from string import ascii_letters
from contextlib import contextmanager

from flask_security import current_user
from flask import request, make_response, current_app
from flask_restful.reqparse import Argument, RequestParser

from dsl_parser import tasks
from dsl_parser import exceptions as parser_exceptions
from dsl_parser.functions import is_function
from dsl_parser.constants import INTER_DEPLOYMENT_FUNCTIONS

from cloudify._compat import urlquote, text_type
from cloudify.models_states import VisibilityState
from cloudify.snapshots import SNAPSHOT_RESTORE_FLAG_FILE

from manager_rest.storage import models
from manager_rest.constants import REST_SERVICE_NAME
from manager_rest.dsl_functions import (get_secret_method,
                                        evaluate_intrinsic_functions)
from manager_rest import manager_exceptions, config, app_context
from manager_rest.utils import is_administrator, get_formatted_timestamp


states_except_private = copy.deepcopy(VisibilityState.STATES)
states_except_private.remove('private')
VISIBILITY_EXCEPT_PRIVATE = states_except_private


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
    return request_dict


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


def set_restart_task(delay=1, service_management='systemd'):
    current_app.logger.info('Restarting the rest service')
    service_command = 'systemctl'
    if service_management == 'supervisord':
        service_command = 'supervisorctl -c /etc/supervisord.conf'
    cmd = 'sleep {0}; sudo {1} restart {2}' \
        .format(delay, service_command, REST_SERVICE_NAME)

    subprocess.Popen(cmd, shell=True)


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
                        runtime_only_evaluation=False):
    try:
        return tasks.prepare_deployment_plan(
            parsed_deployment, get_secret_method, inputs=inputs,
            runtime_only_evaluation=runtime_only_evaluation)
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

    source_deployment = storage_manager.get(models.Deployment, deployment_id)
    for dependency_creator, target_deployment_attr \
            in new_dependencies_dict.items():
        target_deployment_id = target_deployment_attr[0]
        target_deployment_func = target_deployment_attr[1]
        target_deployment = storage_manager.get(
            models.Deployment, target_deployment_id) \
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


class RecursiveDeploymentDependencies(object):
    def __init__(self, sm):
        self.graph = None
        self.sm = sm

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
        inv_graph = {}  # invert dependencies graph
        for key, val in self.graph.items():
            for item in val:
                inv_graph.setdefault(item, set()).add(key)
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

    def add_dependency_to_graph(self, source_deployment, target_deployment):
        self.graph.setdefault(target_deployment, set()).add(source_deployment)

    def remove_dependency_from_graph(self,
                                     source_deployment, target_deployment):
        if target_deployment in self.graph and \
                source_deployment in self.graph[target_deployment]:
            self.graph[target_deployment].remove(source_deployment)
            if not self.graph[target_deployment]:
                del self.graph[target_deployment]

    def assert_no_cyclic_dependencies(self,
                                      source_deployment, target_deployment):
        graph = copy.deepcopy(self.graph)
        graph.setdefault(target_deployment, set()).add(source_deployment)

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
                    'Deployment creation results in cyclic inter-deployment '
                    'dependencies.')
            recursion_stack.append(v)

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
        return sm.get(models.Deployment, target_dep_id, fail_silently=True)

    return None

#########
# Copyright (c) 2019 Cloudify Technologies Ltd. All rights reserved
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

import uuid
from datetime import datetime

from flask import request

from cloudify.models_states import ExecutionState
from manager_rest.rest.responses_v3 import ItemsCount

from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.rest import resources_v2, rest_decorators
from manager_rest.manager_exceptions import BadParametersError
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest.rest_utils import (
    get_json_and_verify_params,
    verify_and_convert_bool,
    parse_datetime_multiple_formats
)
from manager_rest.storage import models, get_storage_manager, ListResult
from manager_rest.workflow_executor import (
    get_amqp_client,
    workflow_sendhandler
)


class Executions(resources_v2.Executions):
    @authorize('execution_delete')
    @rest_decorators.marshal_with(ItemsCount)
    @rest_decorators.create_filters(models.Execution)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
    def delete(self, filters=None, pagination=None, all_tenants=None):
        request_dict = get_json_and_verify_params({
            'keep_last': {'optional': True, 'type': int},
            'to_datetime': {'optional': True}
        })
        if 'keep_last' in request_dict:
            if 'to_datetime' in request_dict:
                raise BadParametersError(
                    "Must provide either a `to_datetime` timestamp or a "
                    "`keep_last` number of executions to keep"
                )
            if request_dict['keep_last'] <= 0:
                raise BadParametersError(
                    "`keep_last` must be an integer greater than 0. got {} "
                    "instead.".format(request_dict['keep_last'])
                )
        requested_time = None
        if 'to_datetime' in request_dict:
            requested_time = parse_datetime_multiple_formats(
                request_dict['to_datetime'])
        if 'status' in filters:
            if filters['status'] not in ExecutionState.END_STATES:
                raise BadParametersError(
                    'Can\'t filter by execution status `{0}`. '
                    'Allowed statuses are: {1}'.format(
                        filters['status'], ExecutionState.END_STATES)
                )
        else:
            filters['status'] = ExecutionState.END_STATES

        sm = get_storage_manager()
        executions = sm.list(models.Execution,
                             filters=filters,
                             all_tenants=all_tenants,
                             get_all_results=True)
        dep_creation_execs = {}
        for execution in executions:
            if execution.workflow_id == 'create_deployment_environment' and \
                    execution.status == 'terminated':
                dep_creation_execs[execution.deployment_id] = \
                    dep_creation_execs.get(execution.deployment_id, 0) + 1

        deleted_count = 0
        if requested_time:
            for execution in executions:
                creation_time = datetime.strptime(execution.created_at,
                                                  '%Y-%m-%dT%H:%M:%S.%fZ')

                if creation_time < requested_time and \
                        self._can_delete_execution(execution,
                                                   dep_creation_execs):
                    sm.delete(execution)
                    deleted_count += 1
        else:
            if request_dict.get('keep_last'):
                max_to_delete = len(executions) - request_dict['keep_last']
            for execution in executions:
                if self._can_delete_execution(execution, dep_creation_execs):
                    sm.delete(execution)
                    deleted_count += 1
                    if request_dict.get('keep_last') and deleted_count >= \
                            max_to_delete:
                        break
        return ListResult([{'count': deleted_count}],
                          {'pagination': pagination})

    @staticmethod
    def _can_delete_execution(execution, dep_creation_execs):
        if execution.workflow_id == \
                'create_deployment_environment':
            if dep_creation_execs[execution.deployment_id] <= 1:
                return False
            else:
                dep_creation_execs[execution.deployment_id] -= 1
        return True


class ExecutionsCheck(SecuredResource):
    @authorize('execution_should_start')
    def get(self, execution_id):
        """
        `should_start` - return True if this execution can currently start
        (no system exeuctions / executions under the same deployment are
        currently running)
        """

        sm = get_storage_manager()
        execution = sm.get(models.Execution, execution_id)
        deployment_id = execution.deployment.id
        rm = get_resource_manager()
        return not (rm.check_for_executions(deployment_id, force=False,
                                            queue=True, execution=execution))


class ExecutionGroups(SecuredResource):
    @authorize('execution_group_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.ExecutionGroup)
    @rest_decorators.sortable(models.ExecutionGroup)
    @rest_decorators.create_filters(models.ExecutionGroup)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            all_tenants=None):
        get_all_results = verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        return get_storage_manager().list(
            models.ExecutionGroup,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants,
            get_all_results=get_all_results
        )

    @authorize('execution_group_create')
    @rest_decorators.marshal_with(models.ExecutionGroup, force_get_data=True)
    def post(self):
        request_dict = get_json_and_verify_params({
            'deployment_group_id': {'type': str},
            'workflow_id': {'type': str},
            'default_parameters': {'optional': True},
            'parameters': {'optional': True},
            'force': {'optional': True},
            'concurrency': {'optional': True},
        })
        default_parameters = request_dict.get('default_parameters') or {}
        parameters = request_dict.get('parameters') or {}
        workflow_id = request_dict['workflow_id']
        force = request_dict.get('force') or False
        concurrency = request_dict.get('concurrency', 5)

        sm = get_storage_manager()
        dep_group = sm.get(models.DeploymentGroup,
                           request_dict['deployment_group_id'])
        group = models.ExecutionGroup(
            id=str(uuid.uuid4()),
            deployment_group=dep_group,
            workflow_id=workflow_id,
            created_at=datetime.now(),
            visibility=dep_group.visibility,
            concurrency=concurrency,
        )
        sm.put(group)
        rm = get_resource_manager()
        executions = []
        with sm.transaction():
            for dep in dep_group.deployments:
                params = default_parameters.copy()
                params.update(parameters.get(dep.id) or {})
                execution = models.Execution(
                    workflow_id=workflow_id,
                    deployment=dep,
                    parameters=params,
                    status=ExecutionState.PENDING,
                )
                sm.put(execution)
                executions.append(execution)
                group.executions.append(execution)

        amqp_client = get_amqp_client()
        handler = workflow_sendhandler()
        amqp_client.add_handler(handler)
        with amqp_client:
            for execution in executions[:group.concurrency]:
                rm.execute_workflow(
                    execution,
                    force=force,
                    send_handler=handler,
                    queue=True,  # allow queue, but it will try to run
                )

        with sm.transaction():
            for execution in executions[group.concurrency:]:
                execution.status = ExecutionState.QUEUED
                sm.update(execution, modified_attrs=('status', ))

        return group


class ExecutionGroupsId(SecuredResource):
    @authorize('execution_group_get', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.ExecutionGroup, force_get_data=True)
    @rest_decorators.all_tenants
    def get(self, group_id, _include=None, all_tenants=None):
        return get_storage_manager().get(
            models.ExecutionGroup,
            group_id,
            include=_include,
            all_tenants=all_tenants,
        )

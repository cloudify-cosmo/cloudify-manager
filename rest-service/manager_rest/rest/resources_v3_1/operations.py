#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

from flask_restful.reqparse import Argument

from cloudify._compat import text_type
from cloudify.constants import TERMINATED_STATES

from manager_rest.rest.rest_utils import (
    get_args_and_verify_arguments,
    get_json_and_verify_params,
)
from manager_rest.rest.rest_decorators import (
    marshal_with,
    paginate
)
from manager_rest.storage import (
    get_storage_manager,
    models
)
from manager_rest.security.authorization import authorize
from manager_rest.resource_manager import get_resource_manager
from manager_rest.security import SecuredResource


class Operations(SecuredResource):
    @authorize('operations')
    @marshal_with(models.Operation)
    @paginate
    def get(self, _include=None, pagination=None, **kwargs):
        args = get_args_and_verify_arguments([
            Argument('graph_id', type=text_type, required=True)
        ])
        sm = get_storage_manager()
        graph_id = args.get('graph_id')
        tasks_graph = sm.list(models.TasksGraph, filters={'id': graph_id})[0]
        return sm.list(
            models.Operation,
            filters={'tasks_graph': tasks_graph},
            pagination=pagination,
            include=_include
        )


class OperationsId(SecuredResource):
    @authorize('operations')
    @marshal_with(models.Operation)
    def get(self, operation_id, **kwargs):
        return get_storage_manager().get(models.Operation, operation_id)

    @authorize('operations')
    @marshal_with(models.Operation)
    def put(self, operation_id, **kwargs):
        params = get_json_and_verify_params({
            'name': {'type': text_type, 'required': True},
            'graph_id': {'type': text_type, 'required': True},
            'dependencies': {'type': list, 'required': True},
            'parameters': {'type': dict},
            'type': {'type': text_type}
        })
        operation = get_resource_manager().create_operation(
            operation_id,
            name=params['name'],
            graph_id=params['graph_id'],
            dependencies=params['dependencies'],
            type=params['type'],
            parameters=params['parameters']
        )
        return operation, 201

    @authorize('operations')
    @marshal_with(models.Operation)
    def patch(self, operation_id, **kwargs):
        request_dict = get_json_and_verify_params(
            {'state': {'type': text_type}}
        )
        sm = get_storage_manager()
        instance = sm.get(models.Operation, operation_id, locking=True)
        instance.state = request_dict.get('state', instance.state)
        if instance.tasks_graph and instance.tasks_graph.execution:
            execution = instance.tasks_graph.execution
            if execution.finished_operations is not None:
                if instance.state in TERMINATED_STATES:
                    execution.finished_operations += 1
            sm.update(
                execution,
                modified_attrs=('total_operations', 'finished_operations'))
        return sm.update(instance)

    @authorize('operations')
    @marshal_with(models.Operation)
    def delete(self, operation_id, **kwargs):
        sm = get_storage_manager()
        instance = sm.get(models.Operation, operation_id, locking=True)
        if instance.tasks_graph and instance.tasks_graph.execution:
            execution = instance.tasks_graph.execution
            if execution.total_operations:
                execution.total_operations -= 1
                if instance.state in TERMINATED_STATES:
                    execution.finished_operations -= 1
            sm.update(
                execution,
                modified_attrs=('total_operations', 'finished_operations'))
        sm.delete(instance)
        return instance, 200


class TasksGraphs(SecuredResource):
    @authorize('operations')
    @marshal_with(models.TasksGraph)
    @paginate
    def get(self, _include=None, pagination=None, **kwargs):
        args = get_args_and_verify_arguments([
            Argument('execution_id', type=text_type, required=True),
            Argument('name', type=text_type, required=True)
        ])
        sm = get_storage_manager()
        execution_id = args.get('execution_id')
        name = args.get('name')
        execution = sm.list(models.Execution, filters={'id': execution_id})[0]
        return sm.list(
            models.TasksGraph,
            filters={'execution': execution, 'name': name},
            pagination=pagination
        )


class TasksGraphsId(SecuredResource):
    @authorize('operations')
    @marshal_with(models.TasksGraph)
    def post(self, **kwargs):
        params = get_json_and_verify_params({
            'name': {'type': text_type, 'required': True},
            'execution_id': {'type': text_type, 'required': True},
            'operations': {'required': False}
        })
        tasks_graph = get_resource_manager().create_tasks_graph(
            name=params['name'],
            execution_id=params['execution_id'],
            operations=params.get('operations', [])
        )
        return tasks_graph, 201

    @authorize('operations')
    @marshal_with(models.TasksGraph)
    def patch(self, tasks_graph_id, **kwargs):
        request_dict = get_json_and_verify_params(
            {'state': {'type': text_type}}
        )
        sm = get_storage_manager()
        instance = sm.get(models.TasksGraph, tasks_graph_id, locking=True)
        instance.state = request_dict.get('state', instance.state)
        return sm.update(instance)

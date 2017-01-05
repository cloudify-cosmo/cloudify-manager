#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
#

from flask_restful import types
from flask_restful.reqparse import Argument
from flask_restful_swagger import swagger

from manager_rest import manager_exceptions
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.resource_manager import (
    ResourceManager,
    get_resource_manager,
)
from manager_rest.rest import requests_schema
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    marshal_with,
)
from manager_rest.rest.rest_utils import (
    get_args_and_verify_arguments,
    get_json_and_verify_params,
    verify_and_convert_bool,
)
from manager_rest.security import SecuredResource
from manager_rest.storage import (
    get_storage_manager,
    models,
)


class Executions(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(models.Execution.__name__),
        nickname="list",
        notes="Returns a list of executions for the optionally provided "
              "deployment id.",
        parameters=[{'name': 'deployment_id',
                     'description': 'List execution of a specific deployment',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'defaultValue': None,
                     'paramType': 'query'},
                    {'name': 'include_system_workflows',
                     'description': 'Include executions of system workflows',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'bool',
                     'defaultValue': False,
                     'paramType': 'query'}]
    )
    @exceptions_handled
    @marshal_with(models.Execution)
    def get(self, _include=None, **kwargs):
        """List executions"""
        args = get_args_and_verify_arguments(
            [Argument('deployment_id', type=str, required=False),
             Argument('include_system_workflows', type=types.boolean,
                      default=False)]
        )
        if args.deployment_id:
            get_storage_manager().get(
                models.Deployment,
                args.deployment_id,
                include=['id']
            )
        deployment_id_filter = ResourceManager.create_filters_dict(
            deployment_id=args.deployment_id)
        return get_resource_manager().list_executions(
            is_include_system_workflows=args.include_system_workflows,
            include=_include,
            filters=deployment_id_filter).items

    @exceptions_handled
    @marshal_with(models.Execution)
    def post(self, **kwargs):
        """Execute a workflow"""
        request_dict = get_json_and_verify_params({'deployment_id',
                                                   'workflow_id'})

        allow_custom_parameters = verify_and_convert_bool(
            'allow_custom_parameters',
            request_dict.get('allow_custom_parameters', 'false'))
        force = verify_and_convert_bool(
            'force',
            request_dict.get('force', 'false'))

        deployment_id = request_dict['deployment_id']
        workflow_id = request_dict['workflow_id']
        parameters = request_dict.get('parameters', None)

        if parameters is not None and parameters.__class__ is not dict:
            raise manager_exceptions.BadParametersError(
                "request body's 'parameters' field must be a dict but"
                " is of type {0}".format(parameters.__class__.__name__))

        bypass_maintenance = is_bypass_maintenance_mode()
        execution = get_resource_manager().execute_workflow(
            deployment_id, workflow_id, parameters=parameters,
            allow_custom_parameters=allow_custom_parameters, force=force,
            bypass_maintenance=bypass_maintenance)
        return execution, 201


class ExecutionsId(SecuredResource):

    @swagger.operation(
        responseClass=models.Execution,
        nickname="getById",
        notes="Returns the execution state by its id.",
    )
    @exceptions_handled
    @marshal_with(models.Execution)
    def get(self, execution_id, _include=None, **kwargs):
        """
        Get execution by id
        """
        return get_storage_manager().get(
            models.Execution,
            execution_id,
            include=_include
        )

    @swagger.operation(
        responseClass=models.Execution,
        nickname="modify_state",
        notes="Modifies a running execution state (currently, only cancel"
              " and force-cancel are supported)",
        parameters=[{'name': 'body',
                     'description': 'json with an action key. '
                                    'Legal values for action are: [cancel,'
                                    ' force-cancel]',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.ModifyExecutionRequest.__name__,  # NOQA
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @exceptions_handled
    @marshal_with(models.Execution)
    def post(self, execution_id, **kwargs):
        """
        Apply execution action (cancel, force-cancel) by id
        """
        request_dict = get_json_and_verify_params({'action'})
        action = request_dict['action']

        valid_actions = ['cancel', 'force-cancel']

        if action not in valid_actions:
            raise manager_exceptions.BadParametersError(
                'Invalid action: {0}, Valid action values are: {1}'.format(
                    action, valid_actions))

        if action in ('cancel', 'force-cancel'):
            return get_resource_manager().cancel_execution(
                execution_id, action == 'force-cancel')

    @swagger.operation(
        responseClass=models.Execution,
        nickname="updateExecutionStatus",
        notes="Updates the execution's status",
        parameters=[{'name': 'status',
                     'description': "The execution's new status",
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'},
                    {'name': 'error',
                     'description': "An error message. If omitted, "
                                    "error will be updated to an empty "
                                    "string",
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @exceptions_handled
    @marshal_with(models.Execution)
    def patch(self, execution_id, **kwargs):
        """
        Update execution status by id
        """
        request_dict = get_json_and_verify_params({'status'})

        return get_resource_manager().update_execution_status(
            execution_id,
            request_dict['status'],
            request_dict.get('error', '')
        )

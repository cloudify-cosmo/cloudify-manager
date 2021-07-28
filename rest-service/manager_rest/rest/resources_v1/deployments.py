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

from flask_restful_swagger import swagger
from flask_restful.reqparse import Argument
from flask_restful.inputs import boolean

from cloudify.models_states import DeploymentState

from manager_rest import manager_exceptions, workflow_executor
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.dsl_functions import evaluate_deployment_outputs
from manager_rest.rest import (requests_schema,
                               responses)
from manager_rest.storage import (get_storage_manager,
                                  models)
from manager_rest.resource_manager import (ResourceManager,
                                           get_resource_manager)
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.rest.rest_utils import (get_args_and_verify_arguments,
                                          get_json_and_verify_params,
                                          validate_inputs)


class Deployments(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(models.Deployment.__name__),
        nickname="list",
        notes="Returns a list of existing deployments."
    )
    @authorize('deployment_list')
    @marshal_with(models.Deployment)
    def get(self, _include=None, **kwargs):
        """
        List deployments
        """
        return get_storage_manager().list(
            models.Deployment, include=_include).items


class DeploymentsId(SecuredResource):
    @swagger.operation(
        responseClass=models.Deployment,
        nickname="getById",
        notes="Returns a deployment by its id."
    )
    @authorize('deployment_get')
    @marshal_with(models.Deployment)
    def get(self, deployment_id, _include=None, **kwargs):
        """
        Get deployment by id
        """
        if _include:
            if {'labels', 'deployment_groups'}.intersection(_include):
                _include = None
        result = get_storage_manager().get(
            models.Deployment,
            deployment_id,
            include=_include
        )
        return result

    @swagger.operation(
        responseClass=models.Deployment,
        nickname="createDeployment",
        notes="Created a new deployment of the given blueprint.",
        parameters=[{'name': 'body',
                     'description': 'Deployment blue print',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.DeploymentRequest.__name__,
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @authorize('deployment_create')
    @marshal_with(models.Deployment)
    def put(self, deployment_id, **kwargs):
        """
        Create a deployment
        """
        validate_inputs({'deployment_id': deployment_id})
        request_schema = self.create_request_schema()
        request_dict = get_json_and_verify_params(request_schema)
        blueprint_id = request_dict['blueprint_id']
        bypass_maintenance = is_bypass_maintenance_mode()
        args = get_args_and_verify_arguments(
            [Argument('private_resource', type=boolean,
                      default=False)]
        )
        skip_plugins_validation = self.get_skip_plugin_validation_flag(
            request_dict)
        rm = get_resource_manager()
        sm = get_storage_manager()
        blueprint = sm.get(models.Blueprint, blueprint_id)
        rm.cleanup_failed_deployment(deployment_id)
        if not skip_plugins_validation:
            rm.check_blueprint_plugins_installed(blueprint.plan)
        deployment = rm.create_deployment(
            blueprint,
            deployment_id,
            private_resource=args.private_resource,
            visibility=None,
        )
        try:
            rm.execute_workflow(deployment.make_create_environment_execution(
                inputs=request_dict.get('inputs', {}),
            ), bypass_maintenance=bypass_maintenance)
        except manager_exceptions.ExistingRunningExecutionError:
            rm.delete_deployment(deployment)
            raise
        return deployment, 201

    def create_request_schema(self):
        request_schema = {
            'blueprint_id': {},
            'inputs': {'optional': True, 'type': dict}
        }
        return request_schema

    def get_skip_plugin_validation_flag(self, request_dict):
        return True

    @swagger.operation(
        responseClass=models.Deployment,
        nickname="deleteById",
        notes="deletes a deployment by its id.",
        parameters=[{'name': 'force',
                     'description': 'Specifies whether to ignore live nodes,'
                                    'or raise an error upon such nodes '
                                    'instead.',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'boolean',
                     'defaultValue': False,
                     'paramType': 'query'}]
    )
    @authorize('deployment_delete')
    def delete(self, deployment_id, **kwargs):
        """Delete deployment by id"""
        args = get_args_and_verify_arguments([
            Argument('force', type=boolean, default=False),
            Argument('delete_logs', type=boolean, default=False)
        ])

        bypass_maintenance = is_bypass_maintenance_mode()
        sm = get_storage_manager()
        dep = sm.get(models.Deployment, deployment_id)
        dep.deployment_status = DeploymentState.IN_PROGRESS
        sm.update(dep, modified_attrs=('deployment_status',))
        rm = get_resource_manager()
        rm.check_deployment_delete(dep, force=args.force)
        delete_execution = dep.make_delete_environment_execution(
            delete_logs=args.delete_logs)
        rm.execute_workflow(
            delete_execution, bypass_maintenance=bypass_maintenance)
        workflow_executor.delete_source_plugins(dep.id)
        return None, 204


class DeploymentModifications(SecuredResource):

    @swagger.operation(
        responseClass=models.DeploymentModification,
        nickname="modifyDeployment",
        notes="Modify deployment.",
        parameters=[{'name': 'body',
                     'description': 'Deployment modification specification',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.
                    DeploymentModificationRequest.__name__,
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @authorize('deployment_modify')
    @marshal_with(models.DeploymentModification)
    def post(self, **kwargs):
        request_dict = get_json_and_verify_params({
            'deployment_id': {},
            'context': {'optional': True, 'type': dict},
            'nodes': {'optional': True, 'type': dict}
        })
        deployment_id = request_dict['deployment_id']
        context = request_dict.get('context', {})
        nodes = request_dict.get('nodes', {})
        modification = get_resource_manager(). \
            start_deployment_modification(deployment_id, nodes, context)
        return modification, 201

    @swagger.operation(
        responseClass='List[{0}]'.format(
            models.DeploymentModification.__name__),
        nickname="listDeploymentModifications",
        notes="List deployment modifications.",
        parameters=[{'name': 'deployment_id',
                     'description': 'Deployment id',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query'}]
    )
    @authorize('deployment_modification_list')
    @marshal_with(models.DeploymentModification)
    def get(self, _include=None, **kwargs):
        args = get_args_and_verify_arguments(
            [Argument('deployment_id', required=False)]
        )
        deployment_id_filter = ResourceManager.create_filters_dict(
            deployment_id=args.deployment_id)
        return get_storage_manager().list(
            models.DeploymentModification,
            filters=deployment_id_filter,
            include=_include
        ).items


class DeploymentModificationsId(SecuredResource):

    @swagger.operation(
        responseClass=models.DeploymentModification,
        nickname="getDeploymentModification",
        notes="Get deployment modification."
    )
    @authorize('deployment_modification_get')
    @marshal_with(models.DeploymentModification)
    def get(self, modification_id, _include=None, **kwargs):
        return get_storage_manager().get(
            models.DeploymentModification,
            modification_id,
            include=_include
        )


class DeploymentModificationsIdFinish(SecuredResource):

    @swagger.operation(
        responseClass=models.DeploymentModification,
        nickname="finishDeploymentModification",
        notes="Finish deployment modification."
    )
    @authorize('deployment_modification_finish')
    @marshal_with(models.DeploymentModification)
    def post(self, modification_id, **kwargs):
        return get_resource_manager().finish_deployment_modification(
            modification_id)


class DeploymentModificationsIdRollback(SecuredResource):

    @swagger.operation(
        responseClass=models.DeploymentModification,
        nickname="rollbackDeploymentModification",
        notes="Rollback deployment modification."
    )
    @authorize('deployment_modification_rollback')
    @marshal_with(models.DeploymentModification)
    def post(self, modification_id, **kwargs):
        return get_resource_manager().rollback_deployment_modification(
            modification_id)


class DeploymentsIdOutputs(SecuredResource):

    @swagger.operation(
        responseClass=responses.DeploymentOutputs.__name__,
        nickname="get",
        notes="Gets a specific deployment outputs."
    )
    @authorize('deployment_modification_outputs')
    @marshal_with(responses.DeploymentOutputs)
    def get(self, deployment_id, **kwargs):
        """Get deployment outputs"""
        outputs = evaluate_deployment_outputs(deployment_id)
        return dict(deployment_id=deployment_id, outputs=outputs)

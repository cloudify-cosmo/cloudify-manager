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

import pydantic
from typing import Optional, Dict, Any

from flask import request

from cloudify.models_states import DeploymentState

from manager_rest import manager_exceptions, workflow_executor
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.dsl_functions import evaluate_deployment_outputs
from manager_rest.rest import requests_schema, responses, swagger
from manager_rest.storage import (get_storage_manager,
                                  models)
from manager_rest.resource_manager import (ResourceManager,
                                           get_resource_manager)
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.rest.rest_utils import validate_inputs


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


class _DeploymentCreateArgs(pydantic.BaseModel):
    blueprint_id: str
    inputs: Optional[Dict[str, Any]] = {}


class _DeploymentDeleteQuery(pydantic.BaseModel):
    force: Optional[bool] = False
    delete_logs: Optional[bool] = False


class _PrivateResourceArgs(pydantic.BaseModel):
    private_resource: Optional[bool] = False


class DeploymentsId(SecuredResource):
    @swagger.operation(
        responseClass=models.Deployment,
        nickname="getById",
        notes="Returns a deployment by its id."
    )
    @authorize('deployment_get')
    @marshal_with(models.Deployment)
    def get(self, deployment_id, _include=None, **kwargs):
        """Get deployment by id"""
        return get_storage_manager().get(
            models.Deployment, deployment_id, include=_include)

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
        request_dict = _DeploymentCreateArgs.parse_obj(request.json).dict()
        blueprint_id = request_dict['blueprint_id']
        bypass_maintenance = is_bypass_maintenance_mode()
        args = _PrivateResourceArgs.parse_obj(request.args)
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
            exc = deployment.make_create_environment_execution(
                inputs=request_dict.get('inputs', {}))
            messages = rm.prepare_executions(
                [exc], bypass_maintenance=bypass_maintenance)
            workflow_executor.execute_workflow(messages)
        except manager_exceptions.ExistingRunningExecutionError:
            rm.delete_deployment(deployment)
            raise
        return deployment, 201

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
        args = _DeploymentDeleteQuery.parse_obj(request.args)
        bypass_maintenance = is_bypass_maintenance_mode()
        sm = get_storage_manager()
        dep = sm.get(models.Deployment, deployment_id)
        dep.deployment_status = DeploymentState.IN_PROGRESS
        sm.update(dep, modified_attrs=('deployment_status',))
        rm = get_resource_manager()
        rm.check_deployment_delete(dep, force=args.force)
        delete_execution = dep.make_delete_environment_execution(
            delete_logs=args.delete_logs,
            force=args.force,
        )
        messages = rm.prepare_executions(
            [delete_execution], bypass_maintenance=bypass_maintenance)
        workflow_executor.execute_workflow(messages)
        workflow_executor.delete_source_plugins(dep.id)
        return "", 204


class _DeploymentModificationArgs(pydantic.BaseModel):
    deployment_id: str
    context: Optional[Dict[str, Any]] = {}
    nodes: Optional[Dict[str, Any]] = {}


class _DeploymentIDArgs(pydantic.BaseModel):
    deployment_id: Optional[str] = None


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
        args = _DeploymentModificationArgs.parse_obj(request.json)
        modification = get_resource_manager().start_deployment_modification(
            args.deployment_id,
            args.nodes,
            args.context,
        )
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
        args = _DeploymentIDArgs.parse_obj(request.args)
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

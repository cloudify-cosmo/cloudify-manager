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

import os
import shutil

from flask import current_app
from flask_restful import types
from flask_restful.reqparse import Argument
from flask_restful_swagger import swagger


from manager_rest import config
from manager_rest.constants import CURRENT_TENANT_CONFIG
from manager_rest.constants import FILE_SERVER_DEPLOYMENTS_FOLDER
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.dsl_functions import evaluate_deployment_outputs
from manager_rest.resource_manager import (
    ResourceManager,
    get_resource_manager,
)
from manager_rest.rest import (
    requests_schema,
    responses,
)
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    marshal_with,
)
from manager_rest.rest.rest_utils import (
    get_args_and_verify_arguments,
    get_json_and_verify_params,
)
from manager_rest.security import SecuredResource
from manager_rest.storage import (
    get_storage_manager,
    models,
)


class Deployments(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(models.Deployment.__name__),
        nickname="list",
        notes="Returns a list of existing deployments."
    )
    @exceptions_handled
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
    @exceptions_handled
    @marshal_with(models.Deployment)
    def get(self, deployment_id, _include=None, **kwargs):
        """
        Get deployment by id
        """
        return get_storage_manager().get(
            models.Deployment,
            deployment_id,
            include=_include
        )

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
    @exceptions_handled
    @marshal_with(models.Deployment)
    def put(self, deployment_id, **kwargs):
        """
        Create a deployment
        """
        request_schema = self.create_request_schema()
        request_dict = get_json_and_verify_params(request_schema)
        blueprint_id = request_dict['blueprint_id']
        bypass_maintenance = is_bypass_maintenance_mode()
        args = get_args_and_verify_arguments(
            [Argument('private_resource', type=types.boolean, default=False)]
        )
        deployment = get_resource_manager().create_deployment(
            blueprint_id,
            deployment_id,
            inputs=request_dict.get('inputs', {}),
            bypass_maintenance=bypass_maintenance,
            private_resource=args.private_resource,
            skip_plugins_validation=self.get_skip_plugin_validation_flag(
                request_dict)
            )
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
        parameters=[{'name': 'ignore_live_nodes',
                     'description': 'Specifies whether to ignore live nodes,'
                                    'or raise an error upon such nodes '
                                    'instead.',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'boolean',
                     'defaultValue': False,
                     'paramType': 'query'}]
    )
    @exceptions_handled
    @marshal_with(models.Deployment)
    def delete(self, deployment_id, **kwargs):
        """
        Delete deployment by id
        """
        args = get_args_and_verify_arguments(
            [Argument('ignore_live_nodes', type=types.boolean, default=False)]
        )

        bypass_maintenance = is_bypass_maintenance_mode()

        deployment = get_resource_manager().delete_deployment(
            deployment_id, bypass_maintenance, args.ignore_live_nodes)

        # Delete deployment resources from file server
        deployment_folder = os.path.join(
            config.instance.file_server_root,
            FILE_SERVER_DEPLOYMENTS_FOLDER,
            current_app.config[CURRENT_TENANT_CONFIG].name,
            deployment.id)
        if os.path.exists(deployment_folder):
            shutil.rmtree(deployment_folder)

        return deployment, 200


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
    @exceptions_handled
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
    @exceptions_handled
    @marshal_with(models.DeploymentModification)
    def get(self, _include=None, **kwargs):
        args = get_args_and_verify_arguments(
            [Argument('deployment_id', type=str, required=False)]
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
    @exceptions_handled
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
    @exceptions_handled
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
    @exceptions_handled
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
    @exceptions_handled
    @marshal_with(responses.DeploymentOutputs)
    def get(self, deployment_id, **kwargs):
        """Get deployment outputs"""
        outputs = evaluate_deployment_outputs(deployment_id)
        return dict(deployment_id=deployment_id, outputs=outputs)

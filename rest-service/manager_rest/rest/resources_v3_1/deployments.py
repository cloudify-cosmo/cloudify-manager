#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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
from builtins import staticmethod
from os.path import join

from flask import request
from flask_restful.inputs import boolean
from flask_restful_swagger import swagger
from flask_restful.reqparse import Argument

from cloudify._compat import text_type
from cloudify.models_states import VisibilityState
from cloudify.constants import SHARED_RESOURCE, COMPONENT
from cloudify.deployment_dependencies import (create_deployment_dependency,
                                              dependency_creator_generator,
                                              DEPENDENCY_CREATOR,
                                              SOURCE_DEPLOYMENT,
                                              TARGET_DEPLOYMENT)

from manager_rest import utils, manager_exceptions
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.manager_exceptions import BadParametersError
from manager_rest.resource_manager import get_resource_manager
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.dsl_functions import evaluate_deployment_capabilities
from manager_rest.rest import (
    rest_utils,
    resources_v1,
    rest_decorators,
    responses_v3
)
from manager_rest.constants import FILE_SERVER_BLUEPRINTS_FOLDER

SHARED_RESOURCE_TYPE = 'cloudify.nodes.SharedResource'
COMPONENT_TYPE = 'cloudify.nodes.Component'


class DeploymentsId(resources_v1.DeploymentsId):

    def create_request_schema(self):
        request_schema = super(DeploymentsId, self).create_request_schema()
        request_schema['skip_plugins_validation'] = {
            'optional': True, 'type': bool}
        request_schema['site_name'] = {'optional': True, 'type': text_type}
        request_schema['runtime_only_evaluation'] = {
            'optional': True, 'type': bool
        }
        return request_schema

    def get_skip_plugin_validation_flag(self, request_dict):
        return request_dict.get('skip_plugins_validation', False)

    @authorize('deployment_create')
    @rest_decorators.marshal_with(models.Deployment)
    def put(self, deployment_id, **kwargs):
        """
        Create a deployment
        """
        rest_utils.validate_inputs({'deployment_id': deployment_id})
        request_schema = self.create_request_schema()
        request_dict = rest_utils.get_json_and_verify_params(request_schema)
        blueprint_id = request_dict['blueprint_id']
        bypass_maintenance = is_bypass_maintenance_mode()
        args = rest_utils.get_args_and_verify_arguments(
            [Argument('private_resource', type=boolean)]
        )
        visibility = rest_utils.get_visibility_parameter(
            optional=True,
            valid_values=VisibilityState.STATES
        )
        deployment = get_resource_manager().create_deployment(
            blueprint_id,
            deployment_id,
            inputs=request_dict.get('inputs', {}),
            bypass_maintenance=bypass_maintenance,
            private_resource=args.private_resource,
            visibility=visibility,
            skip_plugins_validation=self.get_skip_plugin_validation_flag(
                request_dict),
            site_name=_get_site_name(request_dict),
            runtime_only_evaluation=request_dict.get(
                'runtime_only_evaluation', False)
        )
        return deployment, 201


class DeploymentsSetVisibility(SecuredResource):

    @authorize('deployment_set_visibility')
    @rest_decorators.marshal_with(models.Deployment)
    def patch(self, deployment_id):
        """
        Set the deployment's visibility
        """
        visibility = rest_utils.get_visibility_parameter()
        return get_resource_manager().set_deployment_visibility(
            deployment_id,
            visibility
        )


class DeploymentsIdCapabilities(SecuredResource):

    @swagger.operation(
        responseClass=responses_v3.DeploymentCapabilities.__name__,
        nickname="get",
        notes="Gets a specific deployment's capabilities."
    )
    @authorize('deployment_capabilities')
    @rest_decorators.marshal_with(responses_v3.DeploymentCapabilities)
    def get(self, deployment_id, **kwargs):
        """Get deployment capabilities"""
        capabilities = evaluate_deployment_capabilities(deployment_id)
        return dict(deployment_id=deployment_id, capabilities=capabilities)


class DeploymentsSetSite(SecuredResource):

    @authorize('deployment_set_site')
    @rest_decorators.marshal_with(models.Deployment)
    def post(self, deployment_id):
        """
        Set the deployment's site
        """
        site_name = _get_site_name(request.json)
        storage_manager = get_storage_manager()
        deployment = storage_manager.get(models.Deployment, deployment_id)
        site = None
        if site_name:
            site = storage_manager.get(models.Site, site_name)
            utils.validate_deployment_and_site_visibility(deployment, site)
        self._validate_detach_site(site_name)
        deployment.site = site
        return storage_manager.update(deployment)

    def _validate_detach_site(self, site_name):
        detach_site = request.json.get('detach_site')
        if (site_name and detach_site) or (not site_name and not detach_site):
            raise BadParametersError(
                "Must provide either a `site_name` of a valid site or "
                "`detach_site` with true value for detaching the current "
                "site of the given deployment"
            )


def _get_site_name(request_dict):
    if 'site_name' not in request_dict:
        return None

    site_name = request_dict['site_name']
    rest_utils.validate_inputs({'site_name': site_name})
    return site_name


class InterDeploymentDependencies(SecuredResource):
    @swagger.operation(
        responseClass=models.InterDeploymentDependencies,
        nickname="DeploymentDependenciesCreate",
        notes="Creates an inter-deployment dependency.",
        parameters=utils.create_filter_params_list_description(
            models.InterDeploymentDependencies.response_fields,
            'deployment_dependency')
    )
    @authorize('inter_deployment_dependency_create')
    @rest_decorators.marshal_with(models.InterDeploymentDependencies)
    def put(self):
        """Creates an inter-deployment dependency.

        :param dependency_creator: a string representing the entity that
         is responsible for this dependency (e.g. an intrinsic function
         blueprint path, 'node_instances.some_node_instance', etc.).
        :param source_deployment: source deployment that depends on the target
         deployment.
        :param target_deployment: the deployment that the source deployment
         depends on.
        :return: an InterDeploymentDependency object containing the information
         of the dependency.
        """
        sm = get_storage_manager()
        params = self._get_put_dependency_params(sm)
        now = utils.get_formatted_timestamp()
        deployment_dependency = models.InterDeploymentDependencies(
            id=str(uuid.uuid4()),
            dependency_creator=params[DEPENDENCY_CREATOR],
            source_deployment=params[SOURCE_DEPLOYMENT],
            target_deployment=params[TARGET_DEPLOYMENT],
            created_at=now)
        return sm.put(deployment_dependency)

    @staticmethod
    def _verify_and_get_source_and_target_deployments(sm,
                                                      source_deployment_id,
                                                      target_deployment_id):
        source_deployment = sm.get(models.Deployment,
                                   source_deployment_id,
                                   fail_silently=True)
        if not source_deployment:
            raise manager_exceptions.NotFoundError(
                'Given source deployment with ID `{0}` does not exist.'.format(
                    source_deployment_id)
            )
        target_deployment = sm.get(models.Deployment,
                                   target_deployment_id,
                                   fail_silently=True)
        if not target_deployment:
            raise manager_exceptions.NotFoundError(
                'Given target deployment with ID `{0}` does not exist.'.format(
                    target_deployment_id)
            )
        return source_deployment, target_deployment

    @staticmethod
    def _verify_dependency_params():
        return rest_utils.get_json_and_verify_params({
            DEPENDENCY_CREATOR: {'type': text_type},
            SOURCE_DEPLOYMENT: {'type': text_type},
            TARGET_DEPLOYMENT: {'type': text_type}
        })

    @staticmethod
    def _get_put_dependency_params(sm):
        request_dict = InterDeploymentDependencies._verify_dependency_params()
        source_deployment, target_deployment = InterDeploymentDependencies. \
            _verify_and_get_source_and_target_deployments(
                sm,
                request_dict.get(SOURCE_DEPLOYMENT),
                request_dict.get(TARGET_DEPLOYMENT))
        dependency_params = create_deployment_dependency(
            request_dict.get(DEPENDENCY_CREATOR),
            source_deployment,
            target_deployment)
        return dependency_params

    @swagger.operation(
        responseClass=models.InterDeploymentDependencies,
        nickname="DeploymentDependenciesDelete",
        notes="Deletes an inter-deployment dependency.",
        parameters=utils.create_filter_params_list_description(
            models.InterDeploymentDependencies.response_fields,
            'deployment_dependency')
    )
    @authorize('inter_deployment_dependency_delete')
    @rest_decorators.marshal_with(models.InterDeploymentDependencies)
    def delete(self):
        """Deletes an inter-deployment dependency.

        :param dependency_creator: a string representing the entity that
         is responsible for this dependency (e.g. an intrinsic function
         blueprint path, 'node_instances.some_node_instance', etc.).
        :param source_deployment: source deployment that depends on the target
         deployment.
        :param target_deployment: the deployment that the source deployment
         depends on.
        :return: an InterDeploymentDependency object containing the information
         of the dependency.
        """
        sm = get_storage_manager()
        params = self._get_delete_dependency_params(sm)
        filters = create_deployment_dependency(params[DEPENDENCY_CREATOR],
                                               params[SOURCE_DEPLOYMENT],
                                               params[TARGET_DEPLOYMENT])
        dependency = sm.get(
            models.InterDeploymentDependencies,
            None,
            filters=filters,
            # Locking to make sure to fail here and not during the deletion
            # (for the purpose of clarifying the error in case one occurs).
            locking=True)

        return sm.delete(dependency)

    @staticmethod
    def _get_delete_dependency_params(sm):
        request_dict = InterDeploymentDependencies._verify_dependency_params()
        source_deployment, target_deployment = InterDeploymentDependencies. \
            _verify_and_get_source_and_target_deployments(
                sm,
                request_dict.get(SOURCE_DEPLOYMENT),
                request_dict.get(TARGET_DEPLOYMENT))
        dependency_params = create_deployment_dependency(
            request_dict.get(DEPENDENCY_CREATOR),
            source_deployment,
            target_deployment)
        return dependency_params

    @swagger.operation(
        responseClass='List[{0}]'.format(
            models.InterDeploymentDependencies.__name__),
        nickname="listInterDeploymentDependencies",
        notes='Returns a list of inter-deployment dependencies',
        parameters=utils.create_filter_params_list_description(
            models.InterDeploymentDependencies.response_fields,
            'inter-deployment dependency'
        )
    )
    @authorize('inter_deployment_dependency_list')
    @rest_decorators.marshal_with(models.InterDeploymentDependencies)
    @rest_decorators.create_filters(models.InterDeploymentDependencies)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.InterDeploymentDependencies)
    @rest_decorators.search('id')
    def get(self,
            _include=None,
            filters=None,
            pagination=None,
            sort=None,
            search=None,
            **_):
        """List inter-deployment dependencies"""
        inter_deployment_dependencies = \
            get_storage_manager().list(
                models.InterDeploymentDependencies,
                include=_include,
                filters=filters,
                pagination=pagination,
                sort=sort,
                substr_filters=search
            )
        return inter_deployment_dependencies


class InterDeploymentDependenciesRestore(SecuredResource):
    @authorize('inter_deployment_dependency_create')
    def post(self):
        """
        Updating the inter deployment dependencies table from the specified
        deployment during an upgrade

        """
        data = self._get_request_data()
        deployment_id = data.get('deployment_id')
        runtime_only_evaluation = data.get('runtime_only_evaluation')
        sm = get_storage_manager()
        deployment = sm.get(models.Deployment, deployment_id)
        blueprint = deployment.blueprint
        app_dir = join(FILE_SERVER_BLUEPRINTS_FOLDER,
                       utils.current_tenant.name,
                       blueprint.id)
        app_blueprint = blueprint.main_file_name
        parsed_deployment = rest_utils.get_parsed_deployment(
            blueprint, app_dir, app_blueprint)
        deployment_plan = rest_utils.get_deployment_plan(
            parsed_deployment, deployment.inputs,  runtime_only_evaluation)
        rest_utils.update_deployment_dependencies_from_plan(
            deployment_id, deployment_plan, sm, lambda *_: True)
        if data.get('update_service_composition'):
            self._create_service_composition_dependencies(deployment_plan,
                                                          deployment,
                                                          sm)

    @staticmethod
    def _get_request_data():
        return rest_utils.get_json_and_verify_params({
            'deployment_id': {'type': text_type},
            'update_service_composition': {'type': bool},
            'runtime_only_evaluation': {'type': bool, 'optional': True}
        })

    def _create_service_composition_dependencies(self, deployment_plan,
                                                 deployment, sm):
        for node in deployment_plan['nodes']:
            node_type = node.get('type')
            if node_type in (COMPONENT_TYPE, SHARED_RESOURCE_TYPE):
                target_deployment_id = self._get_target_deployment_id(node)
                prefix = (COMPONENT if node_type == COMPONENT_TYPE
                          else SHARED_RESOURCE)
                suffix = self._get_instance_id(deployment_plan, node)
                target_deployment = sm.get(models.Deployment,
                                           target_deployment_id)
                dependency_creator = dependency_creator_generator(prefix,
                                                                  suffix)
                self._put_deployment_dependency(deployment,
                                                target_deployment,
                                                dependency_creator,
                                                sm)

    @staticmethod
    def _get_target_deployment_id(node):
        resource_config = node['properties']['resource_config']
        return resource_config['deployment']['id']

    @staticmethod
    def _put_deployment_dependency(source_deployment, target_deployment,
                                   dependency_creator, sm):
        now = utils.get_formatted_timestamp()
        deployment_dependency = models.InterDeploymentDependencies(
            id=str(uuid.uuid4()),
            dependency_creator=dependency_creator,
            source_deployment=source_deployment,
            target_deployment=target_deployment,
            created_at=now)
        sm.put(deployment_dependency)

    @staticmethod
    def _get_instance_id(deployment_plan, node):
        for instance in deployment_plan['node_instances']:
            if instance['node_id'] == node['id']:
                return instance['id']

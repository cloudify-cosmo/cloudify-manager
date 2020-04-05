# Copyright (c) 2017-2020 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import uuid

from flask_restful_swagger import swagger
from flask_restful.reqparse import Argument

from cloudify.deployment_dependencies import (create_deployment_dependency,
                                              DEPENDENCY_CREATOR,
                                              SOURCE_DEPLOYMENT,
                                              TARGET_DEPLOYMENT)

from manager_rest.security import SecuredResource
from manager_rest import utils, manager_exceptions
from manager_rest.rest import rest_decorators, rest_utils
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.utils import create_filter_params_list_description
from manager_rest.rest.rest_utils import get_args_and_verify_arguments


class InterDeploymentDependency(SecuredResource):

    @swagger.operation(
        responseClass=models.InterDeploymentDependencies,
        nickname="InterDeploymentDependency",
        notes='Return a single inter-deployment dependency',
        parameters=create_filter_params_list_description(
            models.InterDeploymentDependencies.response_fields,
            'inter-deployment dependency')
    )
    @authorize('inter_deployment_dependency_get')
    @rest_decorators.marshal_with(models.InterDeploymentDependencies)
    def get(self, _include=None):
        """Get an inter-deployment dependency by id"""
        args = get_args_and_verify_arguments([
            Argument(DEPENDENCY_CREATOR, required=True),
            Argument(SOURCE_DEPLOYMENT, required=True),
            Argument(TARGET_DEPLOYMENT, required=True)
        ])
        sm = get_storage_manager()
        dependency_creator = args[DEPENDENCY_CREATOR]
        source_deployment = sm.get(models.Deployment,
                                   args[SOURCE_DEPLOYMENT])
        target_deployment = sm.get(models.Deployment,
                                   args[TARGET_DEPLOYMENT])
        filters = create_deployment_dependency(dependency_creator,
                                               source_deployment,
                                               target_deployment)
        list_of_dependencies = sm.list(
            models.InterDeploymentDependencies,
            filters=filters,
            include=_include).items
        if not list_of_dependencies:
            raise manager_exceptions.NotFoundError(
                'Requested Inter-deployment Dependency with params '
                '`dependency_creator: {0}, source_deployment: {1}, '
                'target_deployment: {2}` was not found.'
                ''.format(dependency_creator,
                          source_deployment.id,
                          target_deployment.id)
            )
        return list_of_dependencies[0]


class InterDeploymentDependencies(SecuredResource):
    @swagger.operation(
        responseClass=models.InterDeploymentDependencies,
        nickname="DeploymentDependenciesCreate",
        notes="Creates an inter-deployment dependency.",
        parameters=create_filter_params_list_description(
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
                'Given source deployment with ID `{0}` does not exist.'
                ''.format(source_deployment_id)
            )
        target_deployment = sm.get(models.Deployment,
                                   target_deployment_id,
                                   fail_silently=True)
        if not target_deployment:
            raise manager_exceptions.NotFoundError(
                'Given target deployment with ID `{0}` does not exist.'
                ''.format(target_deployment_id)
            )
        return source_deployment, target_deployment

    @staticmethod
    def _verify_dependency_params():
        return rest_utils.get_json_and_verify_params({
            DEPENDENCY_CREATOR: {'type': unicode},
            SOURCE_DEPLOYMENT: {'type': unicode},
            TARGET_DEPLOYMENT: {'type': unicode}
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
        parameters=create_filter_params_list_description(
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
        parameters=create_filter_params_list_description(
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

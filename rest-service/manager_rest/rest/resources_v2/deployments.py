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

from manager_rest.rest import (
    resources_v1,
    rest_decorators,
)
from manager_rest.storage import (
    get_storage_manager,
    models,
)
from manager_rest.utils import create_filter_params_list_description


class Deployments(resources_v1.Deployments):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.Deployment.__name__),
        nickname="list",
        notes='Returns a list existing deployments for the optionally provided'
              ' filter parameters: '
              '{0}'.format(models.Deployment),
        parameters=create_filter_params_list_description(
            models.Deployment.response_fields,
            'deployments'
        )
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Deployment)
    @rest_decorators.create_filters(models.Deployment)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Deployment)
    @rest_decorators.all_tenants
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            all_tenants=None, **kwargs):
        """
        List deployments
        """
        return get_storage_manager().list(
            models.Deployment,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants
        )


class DeploymentModifications(resources_v1.DeploymentModifications):
    @swagger.operation(
        responseClass='List[{0}]'.format(
            models.DeploymentModification.__name__),
        nickname="listDeploymentModifications",
        notes='Returns a list of deployment modifications for the optionally '
              'provided filter parameters: {0}'
        .format(models.DeploymentModification),
        parameters=create_filter_params_list_description(
            models.DeploymentModification.response_fields,
            'deployment modifications'
        )
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.DeploymentModification)
    @rest_decorators.create_filters(models.DeploymentModification)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.DeploymentModification)
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List deployment modifications
        """
        return get_storage_manager().list(
            models.DeploymentModification,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )

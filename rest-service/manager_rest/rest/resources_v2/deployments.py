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

from flask import request
from flask_restful_swagger import swagger

from .. import rest_utils
from manager_rest.rest import (
    resources_v1,
    rest_decorators,
)
from manager_rest.storage import (
    get_storage_manager,
    models,
)
from manager_rest.security.authorization import authorize
from manager_rest.utils import create_filter_params_list_description
from manager_rest.rest.filters_utils import get_filter_rules_from_filter_id


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
    @authorize('deployment_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Deployment)
    @rest_decorators.create_filters(models.Deployment)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Deployment)
    @rest_decorators.all_tenants
    @rest_decorators.search_multiple_parameters(
        {'_search': 'id', '_search_name': 'display_name'})
    @rest_decorators.filter_id
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            all_tenants=None, search=None, filter_id=None, **kwargs):
        """
        List deployments
        """
        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        filters = filters or {}
        filters.update(rest_utils.deployment_group_id_filter())
        filter_rules = get_filter_rules_from_filter_id(
            filter_id, models.DeploymentsFilter)
        result = get_storage_manager().list(
            models.Deployment,
            include=_include,
            filters=filters,
            substr_filters=search,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants,
            get_all_results=get_all_results,
            filter_rules=filter_rules
        )

        if _include and 'workflows' in _include:
            # Because we coerce this into a list in the model, but our ORM
            # won't return a model instance when filtering results, we have
            # to coerce this here as well. This is unpleasant.
            for index, item in enumerate(result.items):
                r = item._asdict()
                r['workflows'] = models.Deployment._list_workflows(
                    r['workflows'],
                )
                result.items[index] = r

        return result


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
    @authorize('deployment_modification_list')
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

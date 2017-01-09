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


class Nodes(resources_v1.Nodes):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.Node.__name__),
        nickname="listNodes",
        notes='Returns a nodes list for the optionally provided filter '
              'parameters: {0}'.format(models.Node),
        parameters=create_filter_params_list_description(
            models.Node.response_fields,
            'nodes'
        )
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Node)
    @rest_decorators.create_filters(models.Node)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Node)
    @rest_decorators.all_tenants
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, all_tenants=None, **kwargs):
        """
        List nodes
        """
        return get_storage_manager().list(
            models.Node,
            include=_include,
            pagination=pagination,
            filters=filters,
            sort=sort,
            all_tenants=all_tenants
        )


class NodeInstances(resources_v1.NodeInstances):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.NodeInstance.__name__),
        nickname="listNodeInstances",
        notes='Returns a node instances list for the optionally provided '
              'filter parameters: {0}'
        .format(models.NodeInstance),
        parameters=create_filter_params_list_description(
            models.NodeInstance.response_fields,
            'node instances'
        )
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.NodeInstance)
    @rest_decorators.create_filters(models.NodeInstance)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.NodeInstance)
    @rest_decorators.all_tenants
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, all_tenants=None, **kwargs):
        """
        List node instances
        """
        return get_storage_manager().list(
            models.NodeInstance,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants
        )

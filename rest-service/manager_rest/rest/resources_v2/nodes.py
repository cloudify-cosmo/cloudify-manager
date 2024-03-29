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

from manager_rest.rest import (
    resources_v1,
    rest_decorators,
    rest_utils,
    swagger,
)
from manager_rest.storage import (
    get_storage_manager,
    models,
)
from manager_rest.security.authorization import authorize
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
    @authorize('node_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Node)
    @rest_decorators.create_filters(models.Node)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Node)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, all_tenants=None, search=None, **kwargs):
        """
        List nodes
        """
        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        nodes_list = get_storage_manager().list(
            models.Node,
            include=_include,
            pagination=pagination,
            filters=filters,
            substr_filters=search,
            sort=sort,
            all_tenants=all_tenants,
            get_all_results=get_all_results
        )
        # Update the node instance count to account for group scaling policy
        for node in nodes_list:
            if not hasattr(node, 'deployment'):
                continue
            scale_by = 1
            scaling_groups = node.deployment.scaling_groups
            if not scaling_groups:
                continue
            for group in scaling_groups.values():
                if {node.id, node.host_id} & set(group['members']):
                    scale_by *= group['properties']['planned_instances']
            node.set_actual_planned_node_instances(
                scale_by * node.planned_number_of_instances)
        return nodes_list


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
    @authorize('node_instance_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.NodeInstance)
    @rest_decorators.create_filters(models.NodeInstance)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.NodeInstance)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, all_tenants=None, search=None, **kwargs):
        """
        List node instances
        """
        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        return get_storage_manager().list(
            models.NodeInstance,
            include=_include,
            filters=filters,
            substr_filters=search,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants,
            get_all_results=get_all_results
        )

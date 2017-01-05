#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from flask_restful_swagger import swagger

from . import resources_v1, resources_v2, resources_v2_1, resources_v3

SUPPORTED_API_VERSIONS = [('v1', resources_v1),
                          ('v2', resources_v2),
                          ('v2.1', resources_v2_1),
                          ('v3', resources_v3)]


def setup_resources(api):
    resources_endpoints = {
        'Blueprints': 'blueprints',
        'BlueprintsId': 'blueprints/<string:blueprint_id>',
        'BlueprintsIdArchive': 'blueprints/<string:blueprint_id>/archive',
        'Snapshots': 'snapshots',
        'SnapshotsId': 'snapshots/<string:snapshot_id>',
        'SnapshotsIdArchive': 'snapshots/<string:snapshot_id>/archive',
        'SnapshotsIdRestore': 'snapshots/<string:snapshot_id>/restore',
        'Executions': 'executions',
        'ExecutionsId': 'executions/<string:execution_id>',
        'Deployments': 'deployments',
        'DeploymentsId': 'deployments/<string:deployment_id>',
        'DeploymentsIdOutputs': 'deployments/<string:deployment_id>/outputs',
        'DeploymentModifications': 'deployment-modifications',
        'DeploymentModificationsId': 'deployment-modifications/'
                                     '<string:modification_id>',
        'DeploymentModificationsIdFinish': 'deployment-modifications/'
                                           '<string:modification_id>/finish',
        'DeploymentModificationsIdRollback': 'deployment-modifications/'
                                             '<string:modification_id>/'
                                             'rollback',
        'Nodes': 'nodes',
        'NodeInstances': 'node-instances',
        'NodeInstancesId': 'node-instances/<string:node_instance_id>',
        'Events': 'events',
        'Search': 'search',
        'Status': 'status',
        'ProviderContext': 'provider/context',
        'Version': 'version',
        'EvaluateFunctions': 'evaluate/functions',
        'Tokens': 'tokens',
        'Plugins': 'plugins',
        'PluginsId': 'plugins/<string:plugin_id>',
        'PluginsArchive': 'plugins/<string:plugin_id>/archive',
        'MaintenanceMode': 'maintenance',
        'MaintenanceModeAction': 'maintenance/<string:maintenance_action>',

        'DeploymentUpdate':
            'deployment-updates/<string:id>/update/<string:phase>',
        'DeploymentUpdateId': 'deployment-updates/<string:update_id>',
        'DeploymentUpdates': 'deployment-updates',
        'Tenants': 'tenants',
        'TenantsId': 'tenants/<string:tenant_name>',
        'TenantUsers': 'tenants/users',
        'TenantGroups': 'tenants/user-groups',
        'UserGroups': 'user-groups',
        'UserGroupsId': 'user-groups/<string:group_name>',
        'UserGroupsUsers': 'user-groups/users',
        'Users': 'users',
        'UsersId': 'users/<string:username>',
        'Cluster': 'cluster',
        'ClusterNodes': 'cluster/nodes',
        'ClusterNodesId': 'cluster/nodes/<string:node_id>',
        'Permissions': 'permissions'
    }

    # Set version endpoint as a non versioned endpoint
    api.add_resource(resources_v1.Version, '/api/version', endpoint='version')
    for resource, endpoint_suffix in resources_endpoints.iteritems():
        _set_versioned_urls(api, resource, endpoint_suffix)


def _add_swagger_resource(api, api_version, resource, resource_path):
    """
    This method is based on swagger's
    :func:'flask_restful_swagger.swagger.docs.add_resource' and modifies it to
    support multiple API versions. These changes were made:

    1. This method should be called directly for every API resource created.
    AVOID calling :func:'flask_restful_swagger.swagger.docs', or it will
    override Flask-Restful's 'add_resource' with swagger's implementation!
        e.g. add_swagger_resource(api, api_version, resource, '/v1/endpoint')

    2. This method only registers swagger APIs. A separate call to
    Flask-Restful's 'add_resource' is required in order to register the "real"
    API resource.
        e.g: api.add_resource(resource, endpoint_url)

    3. swagger's endpoint_paths contain the api version now, to support
    multiple versions of the same resource on the same API
    """
    endpoint = swagger.swagger_endpoint(resource, resource_path)
    # Add a .help.json help url
    swagger_path = swagger.extract_swagger_path(resource_path)
    endpoint_path = "{0}_{1}_help_json".format(api_version, resource.__name__)
    api.add_resource(endpoint, "%s.help.json" % swagger_path,
                     endpoint=endpoint_path)
    # Add a .help.html help url
    endpoint_path = "{0}_{1}_help_html".format(api_version, resource.__name__)
    api.add_resource(endpoint, "%s.help.html" % swagger_path,
                     endpoint=endpoint_path)
    swagger.register_once(
        add_resource_func=api.add_resource, apiVersion=api_version,
        swaggerVersion='1.2',
        basePath='http://localhost:8100',
        resourcePath='/', produces=["application/json"],
        endpoint='/api/spec')


def _set_versioned_urls(api, resource_name, endpoint_suffix):
    resource = None
    for version in SUPPORTED_API_VERSIONS:
        version_name, resources_impl = version
        if hasattr(resources_impl, resource_name):
            resource = getattr(resources_impl, resource_name)
        # 'resource' will persist throughout iterations, holding a reference
        # to the latest impl.
        if resource:
            endpoint = '{0}/{1}'.format(version_name, endpoint_suffix)
            url = '/api/{0}'.format(endpoint)
            api.add_resource(resource, url, endpoint=endpoint)
            _add_swagger_resource(api, version_name, resource, url)

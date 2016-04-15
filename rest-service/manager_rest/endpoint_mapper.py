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
from manager_rest import resources, resources_v2
from manager_rest import swagger as rest_swagger

SUPPORTED_API_VERSIONS = [('v1', resources),
                          ('v2', resources_v2)]


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
        'DeploymentUpdates': 'deployment-updates',
        'DeploymentUpdateSteps':
            'deployment-updates/<string:update_id>/step',
        'DeploymentUpdateCommit':
            'deployment-updates/<string:update_id>/commit',
        'DeploymentUpdateFinalizeCommit':
            'deployment-updates/<string:update_id>/finalize_commit'
    }

    for resource, endpoint_suffix in resources_endpoints.iteritems():
        _set_versioned_urls(api, resource, endpoint_suffix)


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
            api.add_resource(resource,
                             url,
                             endpoint=endpoint)
            rest_swagger.add_swagger_resource(api,
                                              version_name,
                                              resource,
                                              url)

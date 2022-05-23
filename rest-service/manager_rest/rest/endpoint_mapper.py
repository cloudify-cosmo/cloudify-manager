from . import (swagger, resources_v1, resources_v2,
               resources_v2_1, resources_v3, resources_v3_1)

SUPPORTED_API_VERSIONS = [('v1', resources_v1),
                          ('v2', resources_v2),
                          ('v2.1', resources_v2_1),
                          ('v3', resources_v3),
                          ('v3.1', resources_v3_1)]


def setup_resources(api):
    resources_endpoints = {
        'Blueprints': 'blueprints',
        'BlueprintsId': 'blueprints/<string:blueprint_id>',
        'BlueprintsIdValidate': 'blueprints/<string:blueprint_id>/validate',
        'BlueprintsIdArchive': 'blueprints/<string:blueprint_id>/archive',
        'BlueprintsSetGlobal': 'blueprints/<string:blueprint_id>/set-global',
        'BlueprintsSetVisibility': 'blueprints/<string:blueprint_id>/'
                                   'set-visibility',
        'BlueprintsIcon': 'blueprints/<string:blueprint_id>/icon',
        'Snapshots': 'snapshots',
        'SnapshotsId': 'snapshots/<string:snapshot_id>',
        'SnapshotsIdArchive': 'snapshots/<string:snapshot_id>/archive',
        'SnapshotsIdRestore': 'snapshots/<string:snapshot_id>/restore',
        'SnapshotsStatus': 'snapshot-status',
        'Executions': 'executions',
        'ExecutionsId': 'executions/<string:execution_id>',
        'ExecutionSchedules': 'execution-schedules',
        'ExecutionSchedulesId': 'execution-schedules/<string:schedule_id>',
        'Deployments': 'deployments',
        'DeploymentsId': 'deployments/<string:deployment_id>',
        'DeploymentsSetSite': 'deployments/<string:deployment_id>/set-site',
        'DeploymentsIdOutputs': 'deployments/<string:deployment_id>/outputs',
        'DeploymentsIdCapabilities':
            'deployments/<string:deployment_id>/capabilities',
        'DeploymentsSetVisibility': 'deployments/<string:deployment_id>/'
                                    'set-visibility',
        'Idp': 'idp',
        'InterDeploymentDependencies':
            'deployments/inter-deployment-dependencies',
        'InterDeploymentDependenciesId':
            'deployments/<string:deployment_id>/inter-deployment-dependencies',
        'DeploymentModifications': 'deployment-modifications',
        'DeploymentModificationsId': 'deployment-modifications/'
                                     '<string:modification_id>',
        'DeploymentModificationsIdFinish': 'deployment-modifications/'
                                           '<string:modification_id>/finish',
        'DeploymentModificationsIdRollback': 'deployment-modifications/'
                                             '<string:modification_id>/'
                                             'rollback',
        'Nodes': 'nodes',
        'NodesId': 'nodes/<string:deployment_id>/<string:node_id>',
        'NodeInstances': 'node-instances',
        'NodeInstancesId': 'node-instances/<string:node_instance_id>',
        'Events': 'events',
        'Status': 'status',
        'OK': 'ok',
        'ProviderContext': 'provider/context',
        'Version': 'version',
        'EvaluateFunctions': 'evaluate/functions',
        'Tokens': 'tokens',
        'TokensId': 'tokens/<string:token_id>',
        'Plugins': 'plugins',
        'PluginsId': 'plugins/<string:plugin_id>',
        'PluginsUpdate':
            'plugins-updates/<string:id>/update/<string:phase>',
        'PluginsUpdateId': 'plugins-updates/<string:update_id>',
        'PluginsUpdates': 'plugins-updates',
        'PluginsArchive': 'plugins/<string:plugin_id>/archive',
        'PluginsSetGlobal': 'plugins/<string:plugin_id>/set-global',
        'PluginsSetVisibility': 'plugins/<string:plugin_id>/set-visibility',
        'PluginsYaml': 'plugins/<string:plugin_id>/yaml',
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
        'User': 'user',
        'Users': 'users',
        'UsersId': 'users/<string:username>',
        'UsersActive': 'users/active/<string:username>',
        'UsersUnlock': 'users/unlock/<string:username>',
        'FileServerAuth': 'file-server-auth',
        'FileServerIndex': 'file-server-index',
        'LdapAuthentication': 'ldap',
        'Secrets': 'secrets',
        'SecretsExport': 'secrets/share/export',
        'SecretsImport': 'secrets/share/import',
        'SecretsKey': 'secrets/<string:key>',
        'SecretsSetGlobal': 'secrets/<string:key>/set-global',
        'SecretsSetVisibility': 'secrets/<string:key>/set-visibility',
        'ManagerConfig': 'config',
        'ManagerConfigId': 'config/<string:name>',
        'Managers': 'managers',
        'ManagersId': 'managers/<string:name>',
        'Agents': 'agents',
        'AgentsName': 'agents/<string:name>',
        'SummarizeDeployments': 'summary/deployments',
        'SummarizeNodes': 'summary/nodes',
        'SummarizeNodeInstances': 'summary/node_instances',
        'SummarizeExecutions': 'summary/executions',
        'SummarizeBlueprints': 'summary/blueprints',
        'SummarizeExecutionSchedules': 'summary/execution_schedules',
        'Operations': 'operations',
        'OperationsId': 'operations/<string:operation_id>',
        'TasksGraphs': 'tasks_graphs',
        'TasksGraphsId': 'tasks_graphs/<string:tasks_graph_id>',
        'ExecutionsCheck': 'executions/<execution_id>/should-start',
        'RabbitMQBrokers': 'brokers',
        'DBNodes': 'db-nodes',
        'RabbitMQBrokersId': 'brokers/<string:name>',
        'License': 'license',
        'LicenseCheck': 'license-check',
        'LogBundles': 'log-bundles',
        'LogBundlesId': 'log-bundles/<string:log_bundle_id>',
        'LogBundlesIdArchive': 'log-bundles/<string:log_bundle_id>/archive',
        'Sites': 'sites',
        'SitesName': 'sites/<string:name>',
        'ClusterStatus': 'cluster-status',
        'DeploymentsLabels': 'labels/deployments',
        'DeploymentsLabelsKey': 'labels/deployments/<string:key>',
        'Permissions': 'permissions',
        'PermissionsRole': 'permissions/<string:role_name>',
        'PermissionsRoleId':
            'permissions/<string:role_name>/<string:permission_name>',
        'BlueprintsFilters': 'filters/blueprints',
        'BlueprintsFiltersId': 'filters/blueprints/<string:filter_id>',
        'DeploymentsFilters': 'filters/deployments',
        'DeploymentsFiltersId': 'filters/deployments/<string:filter_id>',
        'DeploymentGroups': 'deployment-groups',
        'DeploymentGroupsId': 'deployment-groups/<string:group_id>',
        'ExecutionGroups': 'execution-groups',
        'ExecutionGroupsId': 'execution-groups/<string:group_id>',
        'BlueprintsLabels': 'labels/blueprints',
        'BlueprintsLabelsKey': 'labels/blueprints/<string:key>',
        'DeploymentsSearches': 'searches/deployments',
        'BlueprintsSearches': 'searches/blueprints',
        'Workflows': 'workflows',
        'WorkflowsSearches': 'searches/workflows',
        'NodesSearches': 'searches/nodes',
        'NodeTypesSearches': 'searches/node-types',
        'NodeInstancesSearches': 'searches/node-instances',
        'SecretsSearches': 'searches/secrets',
        'CapabilitiesSearches': 'searches/capabilities',
        'ScalingGroupsSearches': 'searches/scaling-groups',
        'CommunityContacts': 'contacts',
    }

    # Set version endpoint as a non versioned endpoint
    api.add_resource(resources_v1.Version, '/api/version', endpoint='version')
    for resource, endpoint_suffix in resources_endpoints.items():
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
            api.add_resource(resource, url, endpoint=endpoint)

            swagger.add_swagger_resource(api, version_name, resource, url)

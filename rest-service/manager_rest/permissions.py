"""This module holds the manager's role & permission specification.

Default roles and permissions that are always available on the manager
are defined here.

During manager installation, users can edit authorization.conf, or add
roles/permissions to config.yaml, to override the defaults listed here.
"""

from manager_rest import constants


ROLES = [
    {
        'name': 'sys_admin',
        'type': 'system_role',
        'description': 'User that can manage Cloudify',
    },
    {
        'name': constants.DEFAULT_TENANT_ROLE,
        'type': 'tenant_role',
        'description': 'Regular user, can perform actions on tenants resources'
    }
]

# default permissions; if not configured otherwise, they will all be attached
# to the sys_admin role only
PERMISSIONS = [
    'administrators',
    'agent_create',
    'agent_get',
    'agent_list',
    'agent_replace_certs',
    'agent_update',
    'all_tenants',
    'audit_log_inject',
    'audit_log_truncate',
    'audit_log_view',
    'blueprint_delete',
    'blueprint_download',
    'blueprint_get',
    'blueprint_list',
    'blueprint_upload',
    'broker_credentials',
    'broker_get',
    'broker_manage',
    'cluster_node_config_update',
    'cluster_status_get',
    'community_contact_create',
    'create_global_resource',
    'create_token',
    'db_nodes_get',
    'delete_token',
    'deployment_capabilities',
    'deployment_create',
    'deployment_delete',
    'deployment_get',
    'deployment_group_create',
    'deployment_group_delete',
    'deployment_group_get',
    'deployment_group_list',
    'deployment_group_update',
    'deployment_list',
    'deployment_modification_finish',
    'deployment_modification_get',
    'deployment_modification_list',
    'deployment_modification_outputs',
    'deployment_modification_rollback',
    'deployment_modify',
    'deployment_set_site',
    'deployment_set_visibility',
    'deployment_update',
    'deployment_update_create',
    'deployment_update_get',
    'deployment_update_list',
    'deployment_update_update',
    'event_create',
    'event_delete',
    'event_list',
    'execute_global_workflow',
    'execution_cancel',
    'execution_delete',
    'execution_get',
    'execution_group_cancel',
    'execution_group_create',
    'execution_group_get',
    'execution_group_list',
    'execution_group_update',
    'execution_list',
    'execution_schedule_create',
    'execution_schedule_get',
    'execution_schedule_list',
    'execution_should_start',
    'execution_start',
    'execution_status_update',
    'file_server_auth',
    'filter_create',
    'filter_delete',
    'filter_get',
    'filter_list',
    'filter_update',
    'functions_evaluate',
    'get_password_hash',
    'getting_started',
    'identity_provider_get',
    'inject_token',
    'inter_deployment_dependency_create',
    'inter_deployment_dependency_delete',
    'inter_deployment_dependency_get',
    'inter_deployment_dependency_list',
    'inter_deployment_dependency_update',
    'labels_list',
    'ldap_set',
    'ldap_status_get',
    'license_list',
    'license_remove',
    'license_upload',
    'list_token',
    'log_bundle_create',
    'log_bundle_delete',
    'log_bundle_download',
    'log_bundle_get',
    'log_bundle_list',
    'log_bundle_status_update',
    'maintenance_mode_get',
    'maintenance_mode_set',
    'manage_others_tokens',
    'manager_config_get',
    'manager_config_put',
    'manager_get',
    'manager_manage',
    'monitoring',
    'node_delete',
    'node_instance_delete',
    'node_instance_get',
    'node_instance_list',
    'node_instance_update',
    'node_list',
    'node_update',
    'operations',
    'plugin_delete',
    'plugin_download',
    'plugin_get',
    'plugin_list',
    'plugin_upload',
    'plugins_update_create',
    'plugins_update_get',
    'plugins_update_list',
    'provider_context_create',
    'provider_context_get',
    'resource_set_global',
    'resource_set_visibility',
    'secret_create',
    'secret_delete',
    'secret_export',
    'secret_get',
    'secret_import',
    'secret_list',
    'secret_update',
    'secrets_provider_create',
    'secrets_provider_credentials',
    'secrets_provider_delete',
    'secrets_provider_get',
    'secrets_provider_list',
    'secrets_provider_update',
    'set_execution_details',
    'set_execution_group_details',
    'set_owner',
    'set_plugin_update_details',
    'set_timestamp',
    'site_create',
    'site_delete',
    'site_get',
    'site_list',
    'site_update',
    'snapshot_create',
    'snapshot_delete',
    'snapshot_download',
    'snapshot_get',
    'snapshot_list',
    'snapshot_restore',
    'snapshot_status_update',
    'snapshot_upload',
    'stage_configure',
    'stage_edit_mode',
    'stage_install_widgets',
    'stage_maintenance_mode',
    'stage_services_status',
    'stage_template_management',
    'status_get',
    'tenant_add_group',
    'tenant_add_user',
    'tenant_create',
    'tenant_delete',
    'tenant_get',
    'tenant_list',
    'tenant_list_get_data',
    'tenant_rabbitmq_credentials',
    'tenant_remove_group',
    'tenant_remove_user',
    'tenant_update_group',
    'tenant_update_user',
    'token_get',
    'user_create',
    'user_delete',
    'user_get',
    'user_get_self',
    'user_group_add_user',
    'user_group_create',
    'user_group_delete',
    'user_group_get',
    'user_group_list',
    'user_group_remove_user',
    'user_group_update',
    'user_list',
    'user_set_activated',
    'user_token',
    'user_unlock',
    'user_update',
    'version_get',
    'widget_agents',
    'widget_blueprintActionButtons',
    'widget_blueprintCatalog',
    'widget_blueprintInfo',
    'widget_blueprintNum',
    'widget_blueprintSources',
    'widget_blueprintUploadButton',
    'widget_blueprints',
    'widget_buttonLink',
    'widget_cloudButton',
    'widget_cloudNum',
    'widget_composerLink',
    'widget_custom_admin',
    'widget_custom_all',
    'widget_custom_sys_admin',
    'widget_deploymentActionButtons',
    'widget_deploymentButton',
    'widget_deploymentInfo',
    'widget_deploymentNum',
    'widget_deployments',
    'widget_deploymentsView',
    'widget_events',
    'widget_eventsFilter',
    'widget_executionNum',
    'widget_executions',
    'widget_executionsStatus',
    'widget_filter',
    'widget_filters',
    'widget_highAvailability',
    'widget_inputs',
    'widget_labels',
    'widget_maintenanceModeButton',
    'widget_managers',
    'widget_nodes',
    'widget_nodesComputeNum',
    'widget_nodesStats',
    'widget_onlyMyResources',
    'widget_outputs',
    'widget_pluginUploadButton',
    'widget_plugins',
    'widget_pluginsCatalog',
    'widget_pluginsNum',
    'widget_secretProviders',
    'widget_secrets',
    'widget_serversNum',
    'widget_serviceButton',
    'widget_sites',
    'widget_sitesMap',
    'widget_snapshots',
    'widget_tenants',
    'widget_text',
    'widget_tokens',
    'widget_topology',
    'widget_userGroups',
    'widget_userManagement',
]

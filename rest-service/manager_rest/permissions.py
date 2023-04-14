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
        'name': 'manager',
        'type': 'tenant_role',
        'description': 'User that can manage tenants',
    },
    {
        'name': constants.DEFAULT_TENANT_ROLE,
        'type': 'tenant_role',
        'description': 'Regular user, can perform actions on tenants resources'
    },
    {
        'name': 'operations',
        'type': 'tenant_role',
        'description': 'User that can deploy and execute workflows, but cannot'
                       ' manage blueprints or plugins.'
    },
    {
        'name': 'viewer',
        'type': 'tenant_role',
        'description': 'User that can only view tenant resources'
    },
    {
        'name': constants.DEFAULT_SYSTEM_ROLE,
        'type': 'system_role',
        'description': 'User exists, but have no permissions'
    },
]

# default permissions; if not configured otherwise, they will all be attached
# to the sys_admin role only
PERMISSIONS = {
    'all_tenants': [
        'sys_admin'
    ],
    'administrators': [
        'sys_admin',
        'manager'
    ],
    'create_global_resource': [
        'sys_admin'
    ],
    'getting_started': [
        'sys_admin'
    ],
    'agent_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'agent_create': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'agent_update': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'agent_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'agent_replace_certs': [
        'sys_admin'
    ],
    'blueprint_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'blueprint_download': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'blueprint_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'blueprint_upload': [
        'sys_admin',
        'manager',
        'user'
    ],
    'blueprint_delete': [
        'sys_admin',
        'manager',
        'user'
    ],
    'cluster_status_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'cluster_node_config_update': [
        'sys_admin'
    ],
    'deployment_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'deployment_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'deployment_create': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'deployment_delete': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'deployment_update': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'deployment_modify': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'deployment_set_site': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'deployment_modification_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'deployment_modification_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'deployment_modification_finish': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'deployment_modification_rollback': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'deployment_modification_outputs': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'deployment_capabilities': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'deployment_update_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'deployment_update_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'deployment_update_create': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'deployment_update_update': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'deployment_group_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'deployment_group_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'deployment_group_create': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'deployment_group_update': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'deployment_group_delete': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'event_create': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'event_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'event_delete': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'execute_global_workflow': [
        'sys_admin',
        'manager'
    ],
    'execution_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'execution_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'execution_start': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'execution_cancel': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'execution_status_update': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'execution_schedule_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'execution_schedule_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'execution_schedule_create': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'execution_group_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'execution_group_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'execution_group_create': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'execution_group_cancel': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'execution_group_update': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'set_execution_group_details': [
        'sys_admin'
    ],
    'file_server_auth': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'functions_evaluate': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'ldap_set': [
        'sys_admin'
    ],
    'ldap_status_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'maintenance_mode_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'maintenance_mode_set': [
        'sys_admin'
    ],
    'manager_config_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'manager_config_put': [
        'sys_admin',
        'manager'
    ],
    'manager_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'manager_manage': [
        'sys_admin'
    ],
    'monitoring': [
        'sys_admin'
    ],
    'broker_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'broker_manage': [
        'sys_admin'
    ],
    'broker_credentials': [
        'sys_admin'
    ],
    'db_nodes_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'node_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'node_update': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'node_delete': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'node_instance_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'node_instance_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'node_instance_update': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'node_instance_delete': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'operations': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'plugin_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'plugin_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'plugin_upload': [
        'sys_admin',
        'manager',
        'user'
    ],
    'plugin_download': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'plugin_delete': [
        'sys_admin',
        'manager',
        'user'
    ],
    'plugins_update_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'plugins_update_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'plugins_update_create': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'provider_context_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'provider_context_create': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'secret_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'secret_create': [
        'sys_admin',
        'manager',
        'user'
    ],
    'secret_update': [
        'sys_admin',
        'manager',
        'user'
    ],
    'secret_delete': [
        'sys_admin',
        'manager',
        'user'
    ],
    'secret_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'secret_export': [
        'sys_admin',
        'manager',
        'user'
    ],
    'secret_import': [
        'sys_admin',
        'manager',
        'user'
    ],
    'status_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'site_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'site_create': [
        'sys_admin',
        'manager',
        'user'
    ],
    'site_update': [
        'sys_admin',
        'manager',
        'user'
    ],
    'site_delete': [
        'sys_admin',
        'manager',
        'user'
    ],
    'site_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'tenant_rabbitmq_credentials': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'tenant_get': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'tenant_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'tenant_list_get_data': [
        'sys_admin'
    ],
    'tenant_create': [
        'sys_admin'
    ],
    'tenant_delete': [
        'sys_admin'
    ],
    'tenant_add_user': [
        'sys_admin'
    ],
    'tenant_update_user': [
        'sys_admin'
    ],
    'tenant_remove_user': [
        'sys_admin'
    ],
    'tenant_add_group': [
        'sys_admin'
    ],
    'tenant_update_group': [
        'sys_admin'
    ],
    'tenant_remove_group': [
        'sys_admin'
    ],
    'token_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'user_get': [
        'sys_admin'
    ],
    'user_get_self': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'user_list': [
        'sys_admin'
    ],
    'user_create': [
        'sys_admin'
    ],
    'user_delete': [
        'sys_admin'
    ],
    'user_update': [
        'sys_admin'
    ],
    'user_set_activated': [
        'sys_admin'
    ],
    'user_unlock': [
        'sys_admin'
    ],
    'user_group_get': [
        'sys_admin'
    ],
    'user_group_list': [
        'sys_admin'
    ],
    'user_group_create': [
        'sys_admin'
    ],
    'user_group_delete': [
        'sys_admin'
    ],
    'user_group_update': [
        'sys_admin'
    ],
    'user_group_add_user': [
        'sys_admin'
    ],
    'user_group_remove_user': [
        'sys_admin'
    ],
    'version_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'snapshot_get': [
        'sys_admin'
    ],
    'snapshot_list': [
        'sys_admin'
    ],
    'snapshot_create': [
        'sys_admin'
    ],
    'snapshot_delete': [
        'sys_admin'
    ],
    'snapshot_upload': [
        'sys_admin'
    ],
    'snapshot_download': [
        'sys_admin'
    ],
    'snapshot_status_update': [
        'sys_admin'
    ],
    'snapshot_restore': [
        'sys_admin'
    ],
    'resource_set_global': [
        'sys_admin'
    ],
    'resource_set_visibility': [
        'sys_admin',
        'manager',
        'user'
    ],
    'deployment_set_visibility': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'inter_deployment_dependency_create': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'inter_deployment_dependency_update': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'inter_deployment_dependency_delete': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'inter_deployment_dependency_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'inter_deployment_dependency_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'labels_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'filter_create': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'filter_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'filter_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'filter_update': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'filter_delete': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'stage_services_status': [
        'sys_admin'
    ],
    'stage_edit_mode': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'stage_maintenance_mode': [
        'sys_admin'
    ],
    'stage_configure': [
        'sys_admin'
    ],
    'stage_template_management': [
        'sys_admin'
    ],
    'stage_install_widgets': [
        'sys_admin'
    ],
    'widget_custom_admin': [
        'sys_admin',
        'manager'
    ],
    'widget_custom_sys_admin': [
        'sys_admin'
    ],
    'widget_custom_all': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_agents': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_blueprintCatalog': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_blueprintActionButtons': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'widget_blueprintInfo': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_blueprints': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_blueprintSources': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_blueprintNum': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_blueprintUploadButton': [
        'sys_admin',
        'manager',
        'user'
    ],
    'widget_buttonLink': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_composerLink': [
        'sys_admin',
        'manager',
        'user'
    ],
    'widget_cloudButton': [
        'sys_admin',
        'manager',
        'user'
    ],
    'widget_cloudNum': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_deploymentActionButtons': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'widget_deploymentButton': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'widget_deploymentInfo': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_deploymentNum': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_deployments': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_deploymentsView': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_environmentButton': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'widget_events': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_eventsFilter': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_executionLogs': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_executionNum': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_executions': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_executionsStatus': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_filter': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_filters': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_highAvailability': [
        'sys_admin'
    ],
    'widget_inputs': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_labels': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_maintenanceModeButton': [
        'sys_admin'
    ],
    'widget_nodes': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_nodesComputeNum': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_nodesStats': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_onlyMyResources': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'widget_outputs': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_plugins': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_pluginsCatalog': [
        'sys_admin',
        'manager',
        'user'
    ],
    'widget_pluginsNum': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_pluginUploadButton': [
        'sys_admin',
        'manager',
        'user'
    ],
    'widget_secretProviders': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'widget_secrets': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_serversNum': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_serviceButton': [
        'sys_admin',
        'manager',
        'user'
    ],
    'widget_sites': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_sitesMap': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_snapshots': [
        'sys_admin'
    ],
    'widget_tenants': [
        'sys_admin'
    ],
    'widget_text': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_tokens': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_topology': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'widget_userGroups': [
        'sys_admin'
    ],
    'widget_userManagement': [
        'sys_admin'
    ],
    'user_token': [
        'sys_admin'
    ],
    'execution_delete': [
        'sys_admin',
        'manager',
        'user',
        'operations'
    ],
    'execution_should_start': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'license_upload': [
        'sys_admin'
    ],
    'license_remove': [
        'sys_admin'
    ],
    'license_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'get_password_hash': [
        'sys_admin'
    ],
    'set_timestamp': [
        'sys_admin'
    ],
    'set_owner': [
        'sys_admin'
    ],
    'set_execution_details': [
        'sys_admin'
    ],
    'audit_log_view': [
        'sys_admin'
    ],
    'audit_log_truncate': [
        'sys_admin'
    ],
    'audit_log_inject': [
        'sys_admin'
    ],
    'set_plugin_update_details': [
        'sys_admin'
    ],
    'identity_provider_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer',
        'default'
    ],
    'community_contact_create': [
        'sys_admin'
    ],
    'create_token': [
        'sys_admin',
        'manager',
        'user',
        'default',
        'viewer'
    ],
    'delete_token': [
        'sys_admin',
        'manager',
        'user',
        'default',
        'viewer'
    ],
    'list_token': [
        'sys_admin',
        'manager',
        'user',
        'default',
        'viewer'
    ],
    'manage_others_tokens': [
        'sys_admin'
    ],
    'inject_token': [
        'sys_admin'
    ],
    'log_bundle_list': [
        'sys_admin'
    ],
    'log_bundle_get': [
        'sys_admin'
    ],
    'log_bundle_create': [
        'sys_admin'
    ],
    'log_bundle_delete': [
        'sys_admin'
    ],
    'log_bundle_status_update': [
        'sys_admin'
    ],
    'log_bundle_download': [
        'sys_admin'
    ],
    'secrets_provider_credentials': [
        'sys_admin'
    ],
    'secrets_provider_list': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'secrets_provider_create': [
        'sys_admin',
        'manager',
        'user'
    ],
    'secrets_provider_get': [
        'sys_admin',
        'manager',
        'user',
        'operations',
        'viewer'
    ],
    'secrets_provider_update': [
        'sys_admin',
        'manager',
        'user'
    ],
    'secrets_provider_delete': [
        'sys_admin',
        'manager',
        'user'
    ]
}

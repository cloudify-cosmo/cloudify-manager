"""Cloudify 6.4 to 7.0 DB migration

Revision ID: edd6d829a209
Revises: 272e61bf5f4a
Create Date: 2022-10-13 12:23:56.327514

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from manager_rest.storage.models_base import (
    JSONString,
    UTCDateTime,
)


# revision identifiers, used by Alembic.
revision = 'edd6d829a209'
down_revision = '272e61bf5f4a'
branch_labels = None
depends_on = None


config_table = sa.table(
    'config',
    sa.Column('name', sa.Text),
    sa.Column('value', JSONString()),
    sa.Column('schema', JSONString()),
    sa.Column('is_editable', sa.Boolean),
    sa.Column('scope', sa.Text),
)

users_table = sa.table(
    'users',
    sa.Column('created_at', UTCDateTime),
)

# The information about tables, which should be "audited", meaning INSERT,
# UPDATE and DELETE operations on these tables will be logged in the audit_log
# table.  The logging is executed using PostgreSQL trigger function
# write_audit_log, also defined in this file, see the function
# create_functions_write_audit_log().
# The keys in this dictionary define table names, and the values are
# two-element tuples: the first one is a string, which defines which column of
# the table are used to populate audit_log.ref_id column; the second element is
# a list of columns, which are stored in audit_log.ref_identifier (as JSONB).
tables_to_audit = {
    'agents': ('_storage_id', ['_tenant_id', 'id']),
    'blueprints': ('_storage_id', ['_tenant_id', 'id']),
    'blueprints_filters': ('_storage_id', ['_tenant_id', 'id']),
    'blueprints_labels': ('id', ['id']),
    'certificates': ('id', ['id']),
    'deployment_groups': ('_storage_id', ['_tenant_id', 'id']),
    'deployment_groups_labels': ('id', ['id']),
    'deployment_labels_dependencies': ('_storage_id', ['_tenant_id', 'id']),
    'deployment_modifications': ('_storage_id', ['_tenant_id', 'id']),
    'deployment_update_steps': ('_storage_id', ['_tenant_id', 'id']),
    'deployment_updates': ('_storage_id', ['_tenant_id', 'id']),
    'deployments': ('_storage_id', ['_tenant_id', 'id']),
    'deployments_filters': ('_storage_id', ['_tenant_id', 'id']),
    'deployments_labels': ('id', ['id']),
    'execution_groups': ('_storage_id', ['_tenant_id', 'id']),
    'execution_schedules': ('_storage_id', ['_tenant_id', 'id']),
    'executions': ('_storage_id', ['_tenant_id', 'id']),
    'groups': ('id', ['id']),
    'inter_deployment_dependencies': ('_storage_id', ['_tenant_id', 'id']),
    'licenses': ('id', ['id']),
    'maintenance_mode': ('id', ['id']),
    'managers': ('id', ['id']),
    'node_instances': ('_storage_id', ['_tenant_id', 'id']),
    'nodes': ('_storage_id', ['_tenant_id', 'id']),
    'operations': ('_storage_id', ['_tenant_id', 'id']),
    'permissions': ('id', ['id']),
    'plugins': ('_storage_id', ['_tenant_id', 'id']),
    'plugins_states': ('_storage_id', ['_storage_id']),
    'plugins_updates': ('_storage_id', ['_tenant_id', 'id']),
    'roles': ('id', ['id']),
    'secrets': ('_storage_id', ['_tenant_id', 'id']),
    'sites': ('_storage_id', ['_tenant_id', 'name']),
    'snapshots': ('_storage_id', ['_tenant_id', 'id']),
    'tasks_graphs': ('_storage_id', ['_tenant_id', 'id']),
    'tenants': ('id', ['_tenant_id', 'name']),
    'usage_collector': ('id', ['manager_id', 'id']),
    'users': ('id', ['username']),
}


def upgrade():
    add_p_to_pickle_columns()
    add_json_columns()
    upgrade_users_roles_constraints()
    drop_service_management_config()
    add_users_created_at_index()
    create_secrets_providers_table()
    add_secrets_schema()
    add_secrets_provider_options()
    add_secrets_provider_relationship()
    add_s3_client_config()
    add_file_server_type_config()
    add_default_agents_rest_port_config()
    add_blueprint_requirements_column()
    drop_ldap_ca_config()
    add_audit_log_ref_identifier()
    create_functions_write_audit_log()
    update_audit_triggers()
    add_prometheus_url_config()


def downgrade():
    drop_prometheus_url_config()
    revert_audit_triggers()
    drop_functions_write_audit_log()
    drop_audit_log_ref_identifier()
    add_ldap_ca_config()
    drop_blueprint_requirements_column()
    drop_default_agents_rest_port_config()
    drop_file_server_type_config()
    drop_s3_client_config()
    downgrade_users_roles_constraints()
    remove_json_columns()
    remove_p_from_pickle_columns()
    add_service_management_config()
    drop_users_created_at_index()
    drop_secrets_provider_relationship()
    drop_secrets_providers_table()
    drop_secrets_schema()
    drop_secrets_provider_options()


def add_p_to_pickle_columns():
    op.alter_column('blueprints',
                    column_name='plan',
                    new_column_name='plan_p')

    op.alter_column('deployments',
                    column_name='inputs',
                    new_column_name='inputs_p')
    op.alter_column('deployments',
                    column_name='groups',
                    new_column_name='groups_p')
    op.alter_column('deployments',
                    column_name='policy_triggers',
                    new_column_name='policy_triggers_p')
    op.alter_column('deployments',
                    column_name='policy_types',
                    new_column_name='policy_types_p')
    op.alter_column('deployments',
                    column_name='outputs',
                    new_column_name='outputs_p')
    op.alter_column('deployments',
                    column_name='capabilities',
                    new_column_name='capabilities_p')
    op.alter_column('deployments',
                    column_name='scaling_groups',
                    new_column_name='scaling_groups_p')
    op.alter_column('deployments',
                    column_name='workflows',
                    new_column_name='workflows_p')

    op.alter_column('deployment_modifications',
                    column_name='context',
                    new_column_name='context_p')
    op.alter_column('deployment_modifications',
                    column_name='modified_nodes',
                    new_column_name='modified_nodes_p')
    op.alter_column('deployment_modifications',
                    column_name='node_instances',
                    new_column_name='node_instances_p')

    op.alter_column('deployment_updates',
                    column_name='deployment_plan',
                    new_column_name='deployment_plan_p')
    op.alter_column('deployment_updates',
                    column_name='deployment_update_node_instances',
                    new_column_name='deployment_update_node_instances_p')
    op.alter_column('deployment_updates',
                    column_name='deployment_update_deployment',
                    new_column_name='deployment_update_deployment_p')
    op.alter_column('deployment_updates',
                    column_name='central_plugins_to_uninstall',
                    new_column_name='central_plugins_to_uninstall_p')
    op.alter_column('deployment_updates',
                    column_name='central_plugins_to_install',
                    new_column_name='central_plugins_to_install_p')
    op.alter_column('deployment_updates',
                    column_name='deployment_update_nodes',
                    new_column_name='deployment_update_nodes_p')
    op.alter_column('deployment_updates',
                    column_name='modified_entity_ids',
                    new_column_name='modified_entity_ids_p')
    op.alter_column('deployment_updates',
                    column_name='old_inputs',
                    new_column_name='old_inputs_p')
    op.alter_column('deployment_updates',
                    column_name='new_inputs',
                    new_column_name='new_inputs_p')

    op.alter_column('executions',
                    column_name='parameters',
                    new_column_name='parameters_p')

    op.alter_column('nodes',
                    column_name='plugins',
                    new_column_name='plugins_p')
    op.alter_column('nodes',
                    column_name='plugins_to_install',
                    new_column_name='plugins_to_install_p')
    op.alter_column('nodes',
                    column_name='properties',
                    new_column_name='properties_p')
    op.alter_column('nodes',
                    column_name='relationships',
                    new_column_name='relationships_p')
    op.alter_column('nodes',
                    column_name='operations',
                    new_column_name='operations_p')
    op.alter_column('nodes',
                    column_name='type_hierarchy',
                    new_column_name='type_hierarchy_p')

    op.alter_column('node_instances',
                    column_name='relationships',
                    new_column_name='relationships_p')
    op.alter_column('node_instances',
                    column_name='runtime_properties',
                    new_column_name='runtime_properties_p')
    op.alter_column('node_instances',
                    column_name='scaling_groups',
                    new_column_name='scaling_groups_p')

    op.alter_column('plugins',
                    column_name='excluded_wheels',
                    new_column_name='excluded_wheels_p')
    op.alter_column('plugins',
                    column_name='supported_platform',
                    new_column_name='supported_platform_p')
    op.alter_column('plugins',
                    column_name='supported_py_versions',
                    new_column_name='supported_py_versions_p')
    op.alter_column('plugins',
                    column_name='wheels',
                    new_column_name='wheels_p',
                    nullable=True)

    op.alter_column('plugins_updates',
                    column_name='deployments_to_update',
                    new_column_name='deployments_to_update_p')


def add_json_columns():
    op.add_column('blueprints',
                  sa.Column('plan', JSONString()))

    op.add_column('deployments',
                  sa.Column('inputs', JSONString()))
    op.add_column('deployments',
                  sa.Column('groups', JSONString()))
    op.add_column('deployments',
                  sa.Column('policy_triggers', JSONString()))
    op.add_column('deployments',
                  sa.Column('policy_types', JSONString()))
    op.add_column('deployments',
                  sa.Column('outputs', JSONString()))
    op.add_column('deployments',
                  sa.Column('capabilities', JSONString()))
    op.add_column('deployments',
                  sa.Column('scaling_groups', JSONString()))
    op.add_column('deployments',
                  sa.Column('workflows', JSONString()))

    op.add_column('deployment_modifications',
                  sa.Column('context', JSONString()))
    op.add_column('deployment_modifications',
                  sa.Column('modified_nodes', JSONString()))
    op.add_column('deployment_modifications',
                  sa.Column('node_instances', JSONString()))

    op.add_column('deployment_updates',
                  sa.Column('deployment_plan', JSONString()))
    op.add_column('deployment_updates',
                  sa.Column('deployment_update_node_instances', JSONString()))
    op.add_column('deployment_updates',
                  sa.Column('deployment_update_deployment', JSONString()))
    op.add_column('deployment_updates',
                  sa.Column('central_plugins_to_uninstall', JSONString()))
    op.add_column('deployment_updates',
                  sa.Column('central_plugins_to_install', JSONString()))
    op.add_column('deployment_updates',
                  sa.Column('deployment_update_nodes', JSONString()))
    op.add_column('deployment_updates',
                  sa.Column('modified_entity_ids', JSONString()))
    op.add_column('deployment_updates',
                  sa.Column('old_inputs', JSONString()))
    op.add_column('deployment_updates',
                  sa.Column('new_inputs', JSONString()))

    op.add_column('executions',
                  sa.Column('parameters', JSONString()))

    op.add_column('nodes',
                  sa.Column('plugins', JSONString()))
    op.add_column('nodes',
                  sa.Column('plugins_to_install', JSONString()))
    op.add_column('nodes',
                  sa.Column('properties', JSONString()))
    op.add_column('nodes',
                  sa.Column('relationships', JSONString()))
    op.add_column('nodes',
                  sa.Column('operations', JSONString()))
    op.add_column('nodes',
                  sa.Column('type_hierarchy', JSONString()))

    op.add_column('node_instances',
                  sa.Column('relationships', JSONString()))
    op.add_column('node_instances',
                  sa.Column('runtime_properties', JSONString()))
    op.add_column('node_instances',
                  sa.Column('scaling_groups', JSONString()))

    op.add_column('plugins',
                  sa.Column('excluded_wheels', JSONString()))
    op.add_column('plugins',
                  sa.Column('supported_platform', JSONString()))
    op.add_column('plugins',
                  sa.Column('supported_py_versions', JSONString()))
    op.add_column('plugins',
                  sa.Column('wheels', JSONString()))

    op.add_column('plugins_updates',
                  sa.Column('deployments_to_update', JSONString()))


def upgrade_users_roles_constraints():
    op.drop_constraint('users_roles_role_id_fkey',
                       'users_roles', type_='foreignkey')
    op.drop_constraint('users_roles_user_id_fkey',
                       'users_roles', type_='foreignkey')
    op.create_foreign_key(op.f('users_roles_role_id_fkey'),
                          'users_roles', 'roles', ['role_id'], ['id'],
                          ondelete='CASCADE')
    op.create_foreign_key(op.f('users_roles_user_id_fkey'),
                          'users_roles', 'users', ['user_id'], ['id'],
                          ondelete='CASCADE')


def remove_p_from_pickle_columns():
    op.alter_column('blueprints',
                    column_name='plan_p',
                    new_column_name='plan')

    op.alter_column('deployments',
                    column_name='inputs_p',
                    new_column_name='inputs')
    op.alter_column('deployments',
                    column_name='groups_p',
                    new_column_name='groups')
    op.alter_column('deployments',
                    column_name='policy_triggers_p',
                    new_column_name='policy_triggers')
    op.alter_column('deployments',
                    column_name='policy_types_p',
                    new_column_name='policy_types')
    op.alter_column('deployments',
                    column_name='outputs_p',
                    new_column_name='outputs')
    op.alter_column('deployments',
                    column_name='capabilities_p',
                    new_column_name='capabilities')
    op.alter_column('deployments',
                    column_name='scaling_groups_p',
                    new_column_name='scaling_groups')
    op.alter_column('deployments',
                    column_name='workflows_p',
                    new_column_name='workflows')

    op.alter_column('deployment_modifications',
                    column_name='context_p',
                    new_column_name='context')
    op.alter_column('deployment_modifications',
                    column_name='modified_nodes_p',
                    new_column_name='modified_nodes')
    op.alter_column('deployment_modifications',
                    column_name='node_instances_p',
                    new_column_name='node_instances')

    op.alter_column('deployment_updates',
                    column_name='deployment_plan_p',
                    new_column_name='deployment_plan')
    op.alter_column('deployment_updates',
                    column_name='deployment_update_node_instances_p',
                    new_column_name='deployment_update_node_instances')
    op.alter_column('deployment_updates',
                    column_name='deployment_update_deployment_p',
                    new_column_name='deployment_update_deployment')
    op.alter_column('deployment_updates',
                    column_name='central_plugins_to_uninstall_p',
                    new_column_name='central_plugins_to_uninstall')
    op.alter_column('deployment_updates',
                    column_name='central_plugins_to_install_p',
                    new_column_name='central_plugins_to_install')
    op.alter_column('deployment_updates',
                    column_name='deployment_update_nodes_p',
                    new_column_name='deployment_update_nodes')
    op.alter_column('deployment_updates',
                    column_name='modified_entity_ids_p',
                    new_column_name='modified_entity_ids')
    op.alter_column('deployment_updates',
                    column_name='old_inputs_p',
                    new_column_name='old_inputs')
    op.alter_column('deployment_updates',
                    column_name='new_inputs_p',
                    new_column_name='new_inputs')

    op.alter_column('executions',
                    column_name='parameters_p',
                    new_column_name='parameters')

    op.alter_column('nodes',
                    column_name='plugins_p',
                    new_column_name='plugins')
    op.alter_column('nodes',
                    column_name='plugins_to_install_p',
                    new_column_name='plugins_to_install')
    op.alter_column('nodes',
                    column_name='properties_p',
                    new_column_name='properties')
    op.alter_column('nodes',
                    column_name='relationships_p',
                    new_column_name='relationships')
    op.alter_column('nodes',
                    column_name='operations_p',
                    new_column_name='operations')
    op.alter_column('nodes',
                    column_name='type_hierarchy_p',
                    new_column_name='type_hierarchy')

    op.alter_column('node_instances',
                    column_name='relationships_p',
                    new_column_name='relationships')
    op.alter_column('node_instances',
                    column_name='runtime_properties_p',
                    new_column_name='runtime_properties')
    op.alter_column('node_instances',
                    column_name='scaling_groups_p',
                    new_column_name='scaling_groups')

    op.alter_column('plugins',
                    column_name='excluded_wheels_p',
                    new_column_name='excluded_wheels')
    op.alter_column('plugins',
                    column_name='supported_platform_p',
                    new_column_name='supported_platform')
    op.alter_column('plugins',
                    column_name='supported_py_versions_p',
                    new_column_name='supported_py_versions')
    op.alter_column('plugins',
                    column_name='wheels_p',
                    new_column_name='wheels')

    op.alter_column('plugins_updates',
                    column_name='deployments_to_update_p',
                    new_column_name='deployments_to_update')


def remove_json_columns():
    op.drop_column('blueprints', 'plan')

    op.drop_column('deployments', 'inputs')
    op.drop_column('deployments', 'groups')
    op.drop_column('deployments', 'policy_triggers')
    op.drop_column('deployments', 'policy_types')
    op.drop_column('deployments', 'outputs')
    op.drop_column('deployments', 'capabilities')
    op.drop_column('deployments', 'scaling_groups')
    op.drop_column('deployments', 'workflows')

    op.drop_column('deployment_modifications', 'context')
    op.drop_column('deployment_modifications', 'modified_nodes')
    op.drop_column('deployment_modifications', 'node_instances')

    op.drop_column('deployment_updates', 'deployment_plan')
    op.drop_column('deployment_updates', 'deployment_update_node_instances')
    op.drop_column('deployment_updates', 'deployment_update_deployment')
    op.drop_column('deployment_updates', 'central_plugins_to_uninstall')
    op.drop_column('deployment_updates', 'central_plugins_to_install')
    op.drop_column('deployment_updates', 'deployment_update_nodes')
    op.drop_column('deployment_updates', 'modified_entity_ids')
    op.drop_column('deployment_updates', 'old_inputs')
    op.drop_column('deployment_updates', 'new_inputs')

    op.drop_column('executions', 'parameters')

    op.drop_column('nodes', 'plugins')
    op.drop_column('nodes', 'plugins_to_install')
    op.drop_column('nodes', 'properties')
    op.drop_column('nodes', 'relationships')
    op.drop_column('nodes', 'operations')
    op.drop_column('nodes', 'type_hierarchy')

    op.drop_column('node_instances', 'relationships')
    op.drop_column('node_instances', 'runtime_properties')
    op.drop_column('node_instances', 'scaling_groups')

    op.drop_column('plugins', 'excluded_wheels')
    op.drop_column('plugins', 'supported_platform')
    op.drop_column('plugins', 'supported_py_versions')
    op.drop_column('plugins', 'wheels')

    op.drop_column('plugins_updates', 'deployments_to_update')


def downgrade_users_roles_constraints():
    op.drop_constraint(op.f('users_roles_user_id_fkey'), 'users_roles',
                       type_='foreignkey')
    op.drop_constraint(op.f('users_roles_role_id_fkey'), 'users_roles',
                       type_='foreignkey')
    op.create_foreign_key('users_roles_user_id_fkey',
                          'users_roles', 'users', ['user_id'], ['id'])
    op.create_foreign_key('users_roles_role_id_fkey',
                          'users_roles', 'roles', ['role_id'], ['id'])


def drop_service_management_config():
    op.execute(
        config_table.delete().where(
            config_table.c.name == op.inline_literal('service_management')
        )
    )


def add_service_management_config():
    op.bulk_insert(
        config_table,
        [
            {
                'name': 'service_management',
                'value': 'supervisord',
                'scope': 'rest',
                'schema': {'type': 'string'},
                'is_editable': True,
            },
        ]
    )


def create_secrets_providers_table():
    op.create_table(
        'secrets_providers',
        sa.Column(
            'created_at',
            UTCDateTime(),
            nullable=False,
        ),
        sa.Column(
            '_storage_id',
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            'id',
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            'visibility',
            postgresql.ENUM(
                name='visibility_states',
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            'name',
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            'type',
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            'connection_parameters',
            JSONString(),
            nullable=True,
        ),
        sa.Column(
            'updated_at',
            UTCDateTime(),
            nullable=True,
        ),
        sa.Column(
            '_tenant_id',
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            '_creator_id',
            sa.Integer(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['_creator_id'],
            ['users.id'],
            name=op.f('secrets_providers__creator_id_fkey'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['_tenant_id'],
            ['tenants.id'],
            name=op.f('secrets_providers__tenant_id_fkey'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint(
            '_storage_id',
            name=op.f('secrets_providers_pkey'),
        ),
    )
    op.create_index(
        op.f('secrets_providers__creator_id_idx'),
        'secrets_providers',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('secrets_providers__tenant_id_idx'),
        'secrets_providers',
        ['_tenant_id'],
        unique=False,
    )
    op.create_index(
        op.f('secrets_providers_created_at_idx'),
        'secrets_providers',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        op.f('secrets_providers_id_idx'),
        'secrets_providers',
        ['id'],
        unique=False,
    )
    op.create_index(
        op.f('secrets_providers_visibility_idx'),
        'secrets_providers',
        ['visibility'],
        unique=False,
    )


def drop_secrets_providers_table():
    op.drop_index(
        op.f('secrets_providers_visibility_idx'),
        table_name='secrets_providers',
    )
    op.drop_index(
        op.f('secrets_providers_id_idx'),
        table_name='secrets_providers',
    )
    op.drop_index(
        op.f('secrets_providers_created_at_idx'),
        table_name='secrets_providers',
    )
    op.drop_index(
        op.f('secrets_providers__tenant_id_idx'),
        table_name='secrets_providers',
    )
    op.drop_index(
        op.f('secrets_providers__creator_id_idx'),
        table_name='secrets_providers',
    )
    op.drop_table('secrets_providers')


def add_users_created_at_index():
    op.execute(
        users_table
        .update()
        .where(users_table.c.created_at.is_(None))
        .values(created_at=sa.func.now())
    )
    op.alter_column(
        'users', 'created_at',
        existing_type=postgresql.TIMESTAMP(),
        nullable=False,
    )
    op.create_index(
        op.f('users_created_at_idx'),
        'users',
        ['created_at'],
        unique=False,
    )


def drop_users_created_at_index():
    op.drop_index(op.f('users_created_at_idx'), table_name='users')
    op.alter_column(
        'users', 'created_at',
        existing_type=postgresql.TIMESTAMP(),
        nullable=True,
    )


def add_secrets_schema():
    op.add_column('secrets',
                  sa.Column('schema', JSONString(), nullable=True))


def add_secrets_provider_options():
    op.add_column(
        'secrets',
        sa.Column(
            'provider_options',
            sa.Text,
            nullable=True,
        ),
    )


def drop_secrets_schema():
    op.drop_column('secrets', 'schema')


def drop_secrets_provider_options():
    op.drop_column(
        'secrets',
        'provider_options',
    )


def add_secrets_provider_relationship():
    op.add_column(
        'secrets',
        sa.Column(
            '_secrets_provider_fk',
            sa.Integer(),
            nullable=True,
        ),
    )
    op.create_index(
        op.f(
            'secrets__secrets_provider_fk_idx',
        ),
        'secrets',
        [
            '_secrets_provider_fk',
        ],
        unique=False,
    )
    op.create_foreign_key(
        op.f(
            'secrets__secrets_provider_fk_fkey',
        ),
        'secrets',
        'secrets_providers',
        [
            '_secrets_provider_fk',
        ],

        [
            '_storage_id',
        ],
        ondelete='CASCADE',
    )


def drop_secrets_provider_relationship():
    op.drop_constraint(
        op.f(
            'secrets__secrets_provider_fk_fkey'
        ), 'secrets',
        type_='foreignkey',
    )
    op.drop_index(
        op.f(
            'secrets__secrets_provider_fk_idx',
        ),
        table_name='secrets',
    )
    op.drop_column(
        'secrets',
        '_secrets_provider_fk',
    )


def add_default_agents_rest_port_config():
    op.bulk_insert(
        config_table,
        [
            {
                'name': 'default_agent_port',
                'value': 443,
                'scope': 'rest',
                'schema': {"type": "number", "minimum": 1, "maximum": 65535},
                'is_editable': True,
            },
        ]
    )


def drop_default_agents_rest_port_config():
    op.execute(
        config_table.delete().where(
            (config_table.c.name == op.inline_literal('default_agent_port'))
            & (config_table.c.scope == op.inline_literal('rest'))
        )
    )


def add_s3_client_config():
    op.bulk_insert(
        config_table,
        [
            {
                'name': 's3_server_url',
                'value': 'http://fileserver:9000',
                'scope': 'rest',
                'schema': {'type': 'string'},
                'is_editable': True,
            },
            {
                'name': 's3_resources_bucket',
                'value': 'resources',
                'scope': 'rest',
                'schema': {'type': 'string'},
                'is_editable': True,
            },
            {
                'name': 's3_client_timeout',
                'value': 5.0,
                'scope': 'rest',
                'schema': {'type': 'float'},
                'is_editable': True,
            },
        ]
    )


def drop_s3_client_config():
    for key in ['s3_server_url', 's3_resources_bucket', 's3_client_timeout']:
        op.execute(
            config_table.delete().where(
                (config_table.c.name == op.inline_literal(key))
                & (config_table.c.scope == op.inline_literal('rest'))
            )
        )


def drop_ldap_ca_config():
    op.execute(
        config_table.delete().where(
            (config_table.c.name == op.inline_literal('ldap_ca_path'))
            & (config_table.c.scope == op.inline_literal('rest'))
        )
    )


def add_ldap_ca_config():
    op.bulk_insert(config_table, [
            dict(
                name='ldap_ca_path',
                value=op.inline_literal('null'),
                scope='rest',
                schema={'type': 'string'},
                is_editable=True
            )
        ])


def add_file_server_type_config():
    op.bulk_insert(
        config_table,
        [
            {
                'name': 'file_server_type',
                'value': 'local',
                'scope': 'rest',
                'schema': {'type': 'string'},
                'is_editable': True,
            },
        ],
    )


def drop_file_server_type_config():
    op.execute(
        config_table.delete().where(
            (config_table.c.name == op.inline_literal('file_server_type'))
            & (config_table.c.scope == op.inline_literal('rest'))
        )
    )


def add_blueprint_requirements_column():
    op.add_column(
        'blueprints',
        sa.Column('requirements', JSONString(), nullable=True),
    )


def drop_blueprint_requirements_column():
    op.drop_column('blueprints', 'requirements')


def add_prometheus_url_config():
    op.bulk_insert(
        config_table,
        [
            {
                'name': 'prometheus_url',
                'value': 'http://127.0.0.1:9090/monitoring',
                'scope': 'rest',
                'schema': {'type': 'string'},
                'is_editable': True,
            },
        ],
    )


def drop_prometheus_url_config():
    op.execute(
        config_table.delete().where(
            (config_table.c.name == op.inline_literal('prometheus_url'))
            & (config_table.c.scope == op.inline_literal('rest'))
        )
    )


def add_audit_log_ref_identifier():
    op.add_column('audit_log',
                  sa.Column('ref_identifier', sa.dialects.postgresql.JSONB))


def drop_audit_log_ref_identifier():
    op.drop_column('audit_log', 'ref_identifier')


def create_functions_write_audit_log():
    op.execute("""
    CREATE OR REPLACE FUNCTION write_audit_log() RETURNS TRIGGER AS $$
        DECLARE
            -- List of columns to store, the second argument of the function
            _id_columns text[] := tg_argv[1]::text[];
            -- User performing the modification, from external context
            _user text := public.audit_username();
            -- Execution_id performing the modification, from external context
            _execution_id text := public.audit_execution_id();
            _operation audit_operation;
            _record jsonb;
            _ref_identifier jsonb;
        BEGIN
            -- Prepare audit_operation type and a record to be partially stored
            IF (TG_OP = 'INSERT') THEN
                _operation := 'create';
                _record := to_jsonb(NEW);
            ELSEIF (TG_OP = 'UPDATE') THEN
                _operation := 'update';
                _record := to_jsonb(NEW);
            ELSEIF (TG_OP = 'DELETE') THEN
                _operation := 'delete';
                _record := to_jsonb(OLD);
            END IF;

            -- Create a JSONB object containing only selected (_id_columns)
            -- columns from the modified record
            _ref_identifier := (
                SELECT jsonb_object(
                    array_agg(key),
                    array_agg(_record ->> key)
                )
                FROM unnest(_id_columns) id_cols(key)
            );

            -- Write a new entry in the audit_log table; ref_id column is
            -- populated with the content of the ref_table column described
            -- by the first parameter to this function.
            INSERT INTO public.audit_log (ref_table, ref_id, ref_identifier,
                                          operation, creator_name,
                                          execution_id, created_at)
                VALUES (quote_ident(tg_table_name),
                        (_record->>tg_argv[0])::int,
                        _ref_identifier, _operation, _user, _execution_id,
                        now());
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;""")


def drop_functions_write_audit_log():
    op.execute("""DROP FUNCTION write_audit_log;""")


def update_audit_triggers():
    for table_name, (id_field, identifier_fields) in tables_to_audit.items():
        op.execute(f"""
        DROP TRIGGER IF EXISTS audit_{table_name} ON {table_name};
        CREATE TRIGGER audit_{table_name}
        AFTER INSERT OR UPDATE OR DELETE ON {table_name} FOR EACH ROW
        EXECUTE PROCEDURE
        write_audit_log('{id_field}', '{{ {",".join(identifier_fields)} }}');
        """)


def revert_audit_triggers():
    for table_name, (ref_id_field, _) in tables_to_audit.items():
        op.execute(f"""
        DROP TRIGGER IF EXISTS audit_{table_name} ON {table_name};
        CREATE TRIGGER audit_{table_name}
        AFTER INSERT OR UPDATE OR DELETE ON {table_name} FOR EACH ROW
        EXECUTE PROCEDURE
        write_audit_log_{ref_id_field.strip('_')}('{table_name}');
        """)

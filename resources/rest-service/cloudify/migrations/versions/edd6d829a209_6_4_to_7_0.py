"""Cloudify 6.4 to 7.0 DB migration

Revision ID: edd6d829a209
Revises: 272e61bf5f4a
Create Date: 2022-10-13 12:23:56.327514

"""
from datetime import datetime
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


def upgrade():
    add_p_to_pickle_columns()
    add_json_columns()
    upgrade_users_roles_constraints()
    drop_service_management_config()
    add_users_created_at_index()
    create_secrets_providers_table()
    add_secrets_schema()


def downgrade():
    downgrade_users_roles_constraints()
    remove_json_columns()
    remove_p_from_pickle_columns()
    add_service_management_config()
    drop_users_created_at_index()
    drop_secrets_providers_table()
    drop_secrets_schema()


# Upgrade functions

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


# Downgrade functions

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
                    new_column_name='wheels',
                    nullable=False)

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
        .values(created_at=datetime.utcnow())
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


def drop_secrets_schema():
    op.drop_column('secrets', 'schema')

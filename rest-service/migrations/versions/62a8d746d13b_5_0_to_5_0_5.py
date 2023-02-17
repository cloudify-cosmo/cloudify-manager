"""
5_0 to 5_0_5


Revision ID: 62a8d746d13b
Revises: 423a1643f365
Create Date: 2019-08-23 13:36:03.985636

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

from manager_rest.storage.models_base import JSONString, UTCDateTime

# revision identifiers, used by Alembic.
revision = '62a8d746d13b'
down_revision = '423a1643f365'
branch_labels = None
depends_on = None


config_table = table(
    'config',
    column('name', sa.Text),
    column('value', JSONString()),
    column('schema', JSONString()),
    column('is_editable', sa.Boolean),
    column('updated_at', UTCDateTime()),
    column('scope', sa.Text),
)


def upgrade():
    op.add_column(
        'executions',
        sa.Column('blueprint_id', sa.Text(), nullable=True))
    op.add_column(
        'deployments',
        sa.Column('runtime_only_evaluation', sa.Boolean(), nullable=True))
    op.add_column(
        'deployment_updates',
        sa.Column('runtime_only_evaluation', sa.Boolean(), nullable=True))
    op.add_column(
        'node_instances',
        sa.Column('index', sa.Integer(), nullable=True))

    op.bulk_insert(config_table, [
        dict(
            name='ldap_ca_path',
            value=op.inline_literal('null'),
            scope='rest',
            schema={'type': 'string'},
            is_editable=True
        )
    ])

    _create_db_nodes_table()
    _update_managers_table()
    _update_brokers_table()

    op.create_index(
        op.f('node_instances__node_fk_idx'),
        'node_instances',
        ['_node_fk'],
        unique=False)
    op.create_index(
        op.f('nodes__deployment_fk_idx'),
        'nodes',
        ['_deployment_fk'],
        unique=False)
    op.create_index(
        op.f('executions_ended_at_idx'),
        'executions',
        ['ended_at'],
        unique=False,
    )
    op.create_index(
        op.f('executions_token_idx'), 'executions', ['token'], unique=False
    )
    op.create_index(
        op.f('agents__creator_id_idx'), 'agents', ['_creator_id'], unique=False
    )
    op.create_index(
        op.f('agents__node_instance_fk_idx'),
        'agents',
        ['_node_instance_fk'],
        unique=False,
    )
    op.create_index(
        op.f('agents_visibility_idx'), 'agents', ['visibility'], unique=False
    )
    op.create_index(
        op.f('blueprints__creator_id_idx'),
        'blueprints',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('blueprints_visibility_idx'),
        'blueprints',
        ['visibility'],
        unique=False,
    )
    op.create_index(
        op.f('certificates__updater_id_idx'),
        'certificates',
        ['_updater_id'],
        unique=False,
    )
    op.create_index(
        op.f('config__updater_id_idx'), 'config', ['_updater_id'], unique=False
    )
    op.create_index(
        op.f('deployment_modifications__creator_id_idx'),
        'deployment_modifications',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('deployment_modifications__deployment_fk_idx'),
        'deployment_modifications',
        ['_deployment_fk'],
        unique=False,
    )
    op.create_index(
        op.f('deployment_modifications_visibility_idx'),
        'deployment_modifications',
        ['visibility'],
        unique=False,
    )
    op.create_index(
        op.f('deployment_update_steps__creator_id_idx'),
        'deployment_update_steps',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('deployment_update_steps__deployment_update_fk_idx'),
        'deployment_update_steps',
        ['_deployment_update_fk'],
        unique=False,
    )
    op.create_index(
        op.f('deployment_update_steps_visibility_idx'),
        'deployment_update_steps',
        ['visibility'],
        unique=False,
    )
    op.create_index(
        op.f('deployment_updates__creator_id_idx'),
        'deployment_updates',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('deployment_updates__deployment_fk_idx'),
        'deployment_updates',
        ['_deployment_fk'],
        unique=False,
    )
    op.create_index(
        op.f('deployment_updates__execution_fk_idx'),
        'deployment_updates',
        ['_execution_fk'],
        unique=False,
    )
    op.create_index(
        op.f('deployment_updates__new_blueprint_fk_idx'),
        'deployment_updates',
        ['_new_blueprint_fk'],
        unique=False,
    )
    op.create_index(
        op.f('deployment_updates__old_blueprint_fk_idx'),
        'deployment_updates',
        ['_old_blueprint_fk'],
        unique=False,
    )
    op.create_index(
        op.f('deployment_updates_visibility_idx'),
        'deployment_updates',
        ['visibility'],
        unique=False,
    )
    op.create_index(
        op.f('deployments__blueprint_fk_idx'),
        'deployments',
        ['_blueprint_fk'],
        unique=False,
    )
    op.create_index(
        op.f('deployments__creator_id_idx'),
        'deployments',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('deployments__site_fk_idx'),
        'deployments',
        ['_site_fk'],
        unique=False,
    )
    op.create_index(
        op.f('deployments_visibility_idx'),
        'deployments',
        ['visibility'],
        unique=False,
    )
    op.create_index(
        op.f('events__creator_id_idx'), 'events', ['_creator_id'], unique=False
    )
    op.create_index(
        op.f('events_visibility_idx'), 'events', ['visibility'], unique=False
    )
    op.create_index(
        op.f('executions__creator_id_idx'),
        'executions',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('executions__deployment_fk_idx'),
        'executions',
        ['_deployment_fk'],
        unique=False,
    )
    op.create_index(
        op.f('executions_visibility_idx'),
        'executions',
        ['visibility'],
        unique=False,
    )
    op.create_index(
        op.f('groups_tenants_group_id_idx'),
        'groups_tenants',
        ['group_id'],
        unique=False,
    )
    op.create_index(
        op.f('groups_tenants_role_id_idx'),
        'groups_tenants',
        ['role_id'],
        unique=False,
    )
    op.create_index(
        op.f('groups_tenants_tenant_id_idx'),
        'groups_tenants',
        ['tenant_id'],
        unique=False,
    )
    op.create_index(
        op.f('logs__creator_id_idx'), 'logs', ['_creator_id'], unique=False
    )
    op.create_index(
        op.f('logs_visibility_idx'), 'logs', ['visibility'], unique=False
    )
    op.create_index(
        op.f('managers__ca_cert_id_idx'),
        'managers',
        ['_ca_cert_id'],
        unique=False,
    )
    op.create_index(
        op.f('node_instances__creator_id_idx'),
        'node_instances',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('node_instances_visibility_idx'),
        'node_instances',
        ['visibility'],
        unique=False,
    )
    op.create_index(
        op.f('nodes__creator_id_idx'), 'nodes', ['_creator_id'], unique=False
    )
    op.create_index(
        op.f('nodes_visibility_idx'), 'nodes', ['visibility'], unique=False
    )
    op.create_index(
        op.f('operations__creator_id_idx'),
        'operations',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('operations__tasks_graph_fk_idx'),
        'operations',
        ['_tasks_graph_fk'],
        unique=False,
    )
    op.create_index(
        op.f('operations_visibility_idx'),
        'operations',
        ['visibility'],
        unique=False,
    )
    op.create_index(
        op.f('plugins__creator_id_idx'),
        'plugins',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('plugins_visibility_idx'), 'plugins', ['visibility'], unique=False
    )
    op.create_index(
        op.f('plugins_updates__creator_id_idx'),
        'plugins_updates',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('plugins_updates__execution_fk_idx'),
        'plugins_updates',
        ['_execution_fk'],
        unique=False,
    )
    op.create_index(
        op.f('plugins_updates__original_blueprint_fk_idx'),
        'plugins_updates',
        ['_original_blueprint_fk'],
        unique=False,
    )
    op.create_index(
        op.f('plugins_updates__temp_blueprint_fk_idx'),
        'plugins_updates',
        ['_temp_blueprint_fk'],
        unique=False,
    )
    op.create_index(
        op.f('plugins_updates_visibility_idx'),
        'plugins_updates',
        ['visibility'],
        unique=False,
    )
    op.create_index(
        op.f('rabbitmq_brokers__ca_cert_id_idx'),
        'rabbitmq_brokers',
        ['_ca_cert_id'],
        unique=False,
    )
    op.create_index(
        op.f('secrets__creator_id_idx'),
        'secrets',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('secrets_visibility_idx'), 'secrets', ['visibility'], unique=False
    )
    op.create_index(
        op.f('sites__creator_id_idx'), 'sites', ['_creator_id'], unique=False
    )
    op.create_index(
        op.f('sites_visibility_idx'), 'sites', ['visibility'], unique=False
    )
    op.create_index(
        op.f('snapshots__creator_id_idx'),
        'snapshots',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('snapshots_visibility_idx'),
        'snapshots',
        ['visibility'],
        unique=False,
    )
    op.create_index(
        op.f('tasks_graphs__creator_id_idx'),
        'tasks_graphs',
        ['_creator_id'],
        unique=False,
    )
    op.create_index(
        op.f('tasks_graphs__execution_fk_idx'),
        'tasks_graphs',
        ['_execution_fk'],
        unique=False,
    )
    op.create_index(
        op.f('tasks_graphs_visibility_idx'),
        'tasks_graphs',
        ['visibility'],
        unique=False,
    )
    op.create_index(
        op.f('users_tenants_role_id_idx'),
        'users_tenants',
        ['role_id'],
        unique=False,
    )
    op.create_index(
        op.f('users_tenants_tenant_id_idx'),
        'users_tenants',
        ['tenant_id'],
        unique=False,
    )
    op.create_index(
        op.f('users_tenants_user_id_idx'),
        'users_tenants',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        op.f('events_node_id_idx'),
        'events',
        ['node_id'],
        unique=False
    )
    op.create_index(
        op.f('executions_is_system_workflow_idx'),
        'executions',
        ['is_system_workflow'],
        unique=False
    )
    op.create_index(
        op.f('logs_node_id_idx'),
        'logs',
        ['node_id'],
        unique=False
    )
    op.create_index(
        op.f('node_instances_state_idx'),
        'node_instances',
        ['state'],
        unique=False
    )
    op.create_index(
        op.f('tasks_graphs_name_idx'),
        'tasks_graphs',
        ['name'],
        unique=False
    )
    op.create_index(
        'deployments__sife_fk_visibility_idx',
        'deployments',
        ['_blueprint_fk', '_site_fk', 'visibility', '_tenant_id'],
        unique=False
    )
    op.create_index(
        'events_node_id_visibility_idx',
        'events',
        ['node_id', 'visibility'],
        unique=False
    )
    op.create_index(
        'executions_dep_fk_isw_vis_tenant_id_idx',
        'executions',
        ['_deployment_fk', 'is_system_workflow', 'visibility', '_tenant_id'],
        unique=False
    )
    op.create_index(
        'logs_node_id_visibility_execution_fk_idx',
        'logs',
        ['node_id', 'visibility', '_execution_fk'],
        unique=False
    )
    op.create_index(
        'node_instances_state_visibility_idx',
        'node_instances',
        ['state', 'visibility'],
        unique=False
    )
    op.create_index(
        'tasks_graphs__execution_fk_name_visibility_idx',
        'tasks_graphs',
        ['_execution_fk', 'name', 'visibility'],
        unique=False
    )

    op.create_primary_key(
        'users_roles_pkey',
        'users_roles',
        ['user_id', 'role_id'],
    )


def downgrade():
    op.drop_index(
        'tasks_graphs__execution_fk_name_visibility_idx',
        table_name='tasks_graphs'
    )
    op.drop_index(
        'node_instances_state_visibility_idx',
        table_name='node_instances'
    )
    op.drop_index(
        'logs_node_id_visibility_execution_fk_idx',
        table_name='logs'
    )
    op.drop_index(
        'executions_dep_fk_isw_vis_tenant_id_idx',
        table_name='executions'
    )
    op.drop_index(
        'events_node_id_visibility_idx',
        table_name='events'
    )
    op.drop_index(
        'deployments__sife_fk_visibility_idx',
        table_name='deployments'
    )

    op.drop_index(op.f('tasks_graphs_name_idx'), table_name='tasks_graphs')
    op.drop_index(op.f('node_instances_state_idx'),
                  table_name='node_instances')
    op.drop_index(op.f('logs_node_id_idx'), table_name='logs')
    op.drop_index(op.f('executions_is_system_workflow_idx'),
                  table_name='executions')
    op.drop_index(op.f('events_node_id_idx'), table_name='events')
    op.drop_index(
        op.f('users_tenants_user_id_idx'), table_name='users_tenants'
    )
    op.drop_index(
        op.f('users_tenants_tenant_id_idx'), table_name='users_tenants'
    )
    op.drop_index(
        op.f('users_tenants_role_id_idx'), table_name='users_tenants'
    )
    op.drop_index(
        op.f('tasks_graphs_visibility_idx'), table_name='tasks_graphs'
    )
    op.drop_index(
        op.f('tasks_graphs__execution_fk_idx'), table_name='tasks_graphs'
    )
    op.drop_index(
        op.f('tasks_graphs__creator_id_idx'), table_name='tasks_graphs'
    )
    op.drop_index(op.f('snapshots_visibility_idx'), table_name='snapshots')
    op.drop_index(op.f('snapshots__creator_id_idx'), table_name='snapshots')
    op.drop_index(op.f('sites_visibility_idx'), table_name='sites')
    op.drop_index(op.f('sites__creator_id_idx'), table_name='sites')
    op.drop_index(op.f('secrets_visibility_idx'), table_name='secrets')
    op.drop_index(op.f('secrets__creator_id_idx'), table_name='secrets')
    op.drop_index(
        op.f('rabbitmq_brokers__ca_cert_id_idx'), table_name='rabbitmq_brokers'
    )
    op.drop_index(
        op.f('plugins_updates_visibility_idx'), table_name='plugins_updates'
    )
    op.drop_index(
        op.f('plugins_updates__temp_blueprint_fk_idx'),
        table_name='plugins_updates',
    )
    op.drop_index(
        op.f('plugins_updates__original_blueprint_fk_idx'),
        table_name='plugins_updates',
    )
    op.drop_index(
        op.f('plugins_updates__execution_fk_idx'), table_name='plugins_updates'
    )
    op.drop_index(
        op.f('plugins_updates__creator_id_idx'), table_name='plugins_updates'
    )
    op.drop_index(op.f('plugins_visibility_idx'), table_name='plugins')
    op.drop_index(op.f('plugins__creator_id_idx'), table_name='plugins')
    op.drop_index(op.f('operations_visibility_idx'), table_name='operations')
    op.drop_index(
        op.f('operations__tasks_graph_fk_idx'), table_name='operations'
    )
    op.drop_index(op.f('operations__creator_id_idx'), table_name='operations')
    op.drop_index(op.f('nodes_visibility_idx'), table_name='nodes')
    op.drop_index(op.f('nodes__creator_id_idx'), table_name='nodes')
    op.drop_index(
        op.f('node_instances_visibility_idx'), table_name='node_instances'
    )
    op.drop_index(
        op.f('node_instances__creator_id_idx'), table_name='node_instances'
    )
    op.drop_index(op.f('managers__ca_cert_id_idx'), table_name='managers')
    op.drop_index(op.f('logs_visibility_idx'), table_name='logs')
    op.drop_index(op.f('logs__creator_id_idx'), table_name='logs')
    op.drop_index(
        op.f('groups_tenants_tenant_id_idx'), table_name='groups_tenants'
    )
    op.drop_index(
        op.f('groups_tenants_role_id_idx'), table_name='groups_tenants'
    )
    op.drop_index(
        op.f('groups_tenants_group_id_idx'), table_name='groups_tenants'
    )
    op.drop_index(op.f('executions_visibility_idx'), table_name='executions')
    op.drop_index(
        op.f('executions__deployment_fk_idx'), table_name='executions'
    )
    op.drop_index(op.f('executions__creator_id_idx'), table_name='executions')
    op.drop_index(op.f('events_visibility_idx'), table_name='events')
    op.drop_index(op.f('events__creator_id_idx'), table_name='events')
    op.drop_index(op.f('deployments_visibility_idx'), table_name='deployments')
    op.drop_index(op.f('deployments__site_fk_idx'), table_name='deployments')
    op.drop_index(
        op.f('deployments__creator_id_idx'), table_name='deployments'
    )
    op.drop_index(
        op.f('deployments__blueprint_fk_idx'), table_name='deployments'
    )
    op.drop_index(
        op.f('deployment_updates_visibility_idx'),
        table_name='deployment_updates',
    )
    op.drop_index(
        op.f('deployment_updates__old_blueprint_fk_idx'),
        table_name='deployment_updates',
    )
    op.drop_index(
        op.f('deployment_updates__new_blueprint_fk_idx'),
        table_name='deployment_updates',
    )
    op.drop_index(
        op.f('deployment_updates__execution_fk_idx'),
        table_name='deployment_updates',
    )
    op.drop_index(
        op.f('deployment_updates__deployment_fk_idx'),
        table_name='deployment_updates',
    )
    op.drop_index(
        op.f('deployment_updates__creator_id_idx'),
        table_name='deployment_updates',
    )
    op.drop_index(
        op.f('deployment_update_steps_visibility_idx'),
        table_name='deployment_update_steps',
    )
    op.drop_index(
        op.f('deployment_update_steps__deployment_update_fk_idx'),
        table_name='deployment_update_steps',
    )
    op.drop_index(
        op.f('deployment_update_steps__creator_id_idx'),
        table_name='deployment_update_steps',
    )
    op.drop_index(
        op.f('deployment_modifications_visibility_idx'),
        table_name='deployment_modifications',
    )
    op.drop_index(
        op.f('deployment_modifications__deployment_fk_idx'),
        table_name='deployment_modifications',
    )
    op.drop_index(
        op.f('deployment_modifications__creator_id_idx'),
        table_name='deployment_modifications',
    )
    op.drop_index(op.f('config__updater_id_idx'), table_name='config')
    op.drop_index(
        op.f('certificates__updater_id_idx'), table_name='certificates'
    )
    op.drop_index(op.f('blueprints_visibility_idx'), table_name='blueprints')
    op.drop_index(op.f('blueprints__creator_id_idx'), table_name='blueprints')
    op.drop_index(op.f('agents_visibility_idx'), table_name='agents')
    op.drop_index(op.f('agents__node_instance_fk_idx'), table_name='agents')
    op.drop_index(op.f('agents__creator_id_idx'), table_name='agents')
    op.drop_index(op.f('executions_token_idx'), table_name='executions')
    op.drop_index(op.f('executions_ended_at_idx'), table_name='executions')
    op.drop_index(op.f('nodes__deployment_fk_idx'), table_name='nodes')
    op.drop_index(
        op.f('node_instances__node_fk_idx'), table_name='node_instances'
    )

    op.drop_column('deployment_updates', 'runtime_only_evaluation')
    op.drop_column('deployments', 'runtime_only_evaluation')
    op.drop_column('executions', 'blueprint_id')
    op.drop_column('node_instances', 'index')
    op.execute(
        config_table
        .delete()
        .where(
            (config_table.c.name == op.inline_literal('ldap_ca_path')) &
            (config_table.c.scope == op.inline_literal('rest'))
        )
    )
    op.drop_constraint(
        op.f('rabbitmq_brokers_node_id_key'),
        'rabbitmq_brokers',
        type_='unique'
    )
    op.drop_column('rabbitmq_brokers', 'node_id')
    op.drop_column('rabbitmq_brokers', 'is_external')
    op.drop_constraint(
        op.f('managers_node_id_key'),
        'managers',
        type_='unique'
    )
    op.drop_column('managers', 'node_id')
    op.drop_index(op.f('managers_last_seen_idx'), table_name='managers')
    op.drop_column('managers', 'last_seen')
    op.drop_column('managers', 'status_report_frequency')
    op.drop_table('db_nodes')
    op.drop_constraint(
        'users_roles_pkey',
        'users_roles',
    )


def _update_managers_table():
    op.add_column('managers', sa.Column('node_id', sa.Text(), nullable=True))
    op.add_column('managers',
                  sa.Column('last_seen', UTCDateTime(), nullable=False,
                            server_default=sa.func.current_timestamp()))
    op.add_column('managers',
                  sa.Column('status_report_frequency', sa.Integer(),
                            nullable=True))
    op.execute("""
      UPDATE managers
      SET node_id = hostname;
    """)
    op.alter_column('managers', 'node_id', nullable=False)
    op.create_unique_constraint(op.f('managers_node_id_key'), 'managers',
                                ['node_id'])
    op.create_index(op.f('managers_last_seen_idx'), 'managers', ['last_seen'],
                    unique=False)


def _update_brokers_table():
    op.add_column('rabbitmq_brokers',
                  sa.Column('is_external',
                            sa.Boolean(),
                            nullable=False,
                            server_default='f'))
    op.add_column('rabbitmq_brokers',
                  sa.Column('node_id', sa.Text(), nullable=True))
    op.execute("""
      UPDATE rabbitmq_brokers
      SET node_id = name;
    """)
    op.alter_column('rabbitmq_brokers', 'node_id', nullable=False)
    op.create_unique_constraint(op.f('rabbitmq_brokers_node_id_key'),
                                'rabbitmq_brokers', ['node_id'])


def _create_db_nodes_table():
    op.create_table(
        'db_nodes',
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('node_id', sa.Text(), nullable=False),
        sa.Column('host', sa.Text(), nullable=False),
        sa.Column('is_external', sa.Boolean(), nullable=False,
                  server_default='f'),
        sa.PrimaryKeyConstraint('name', name=op.f('db_nodes_pkey')),
        sa.UniqueConstraint('node_id', name=op.f('db_nodes_node_id_key')),
        sa.UniqueConstraint('host', name=op.f('db_nodes_host_key'))
    )

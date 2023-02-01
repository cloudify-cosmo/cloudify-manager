"""5_0_5 to 5_1

- Add usage_collector table
- Adding inter deployment dependencies table
- Add unique indexes
- Remove node_id column from Manager, RabbitMQBroker and DBNodes

Revision ID: 387fcd049efb
Revises: 62a8d746d13b
Create Date: 2020-03-30 06:27:26.747213

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column, expression
from manager_rest import storage
from sqlalchemy.dialects import postgresql

from cloudify.models_states import VisibilityState

from manager_rest.storage.models_base import JSONString, UTCDateTime

# revision identifiers, used by Alembic.
revision = '387fcd049efb'
down_revision = '62a8d746d13b'
branch_labels = None
depends_on = None

VISIBILITY_ENUM = postgresql.ENUM(VisibilityState.PRIVATE,
                                  VisibilityState.TENANT,
                                  VisibilityState.GLOBAL,
                                  name='visibility_states',
                                  create_type=False)

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
    _create_usage_collector_table()
    _create_inter_deployment_dependencies_table()
    _create_unique_indexes()
    _add_plugins_title_column()
    _remove_node_id_columns()
    _add_monitoring_credentials_columns()

    op.bulk_insert(config_table, [
        dict(
            name='service_management',
            value='systemd',
            scope='rest',
            schema=None,
            is_editable=True
        ),
        dict(
            name='blueprint_folder_max_size_mb',
            value=50,
            scope='rest',
            schema={'type': 'number', 'minimum': 0},
            is_editable=True
        ),
        dict(
            name='blueprint_folder_max_files',
            value=10000,
            scope='rest',
            schema={'type': 'number', 'minimum': 0},
            is_editable=True
        ),
        dict(
            name='monitoring_timeout',
            value=4,
            scope='rest',
            schema={'type': 'number', 'minimum': 0},
            is_editable=True
        )
    ])
    _create_plugins_states_table()


def downgrade():
    op.drop_table('plugins_states')
    _remove_monitoring_credentials_columns()
    _drop_usage_collector_table()
    _drop_inter_deployment_dependencies_table()
    _drop_unique_indexes()
    _drop_plugins_title_column()
    _create_node_id_columns()

    op.execute(
        config_table
        .delete()
        .where(
            (config_table.c.name == op.inline_literal('blueprint_folder_max_size_mb')) & # NOQA
            (config_table.c.scope == op.inline_literal('rest'))
        )
    )
    op.execute(
        config_table
        .delete()
        .where(
            (config_table.c.name == op.inline_literal('blueprint_folder_max_files')) &  # NOQA
            (config_table.c.scope == op.inline_literal('rest'))
        )
    )
    op.execute(
        config_table
        .delete()
        .where(
            (config_table.c.name == op.inline_literal('service_management')) &
            (config_table.c.scope == op.inline_literal('rest'))
        )
    )
    op.execute(
        config_table
        .delete()
        .where(
            (config_table.c.name == op.inline_literal('monitoring_timeout')) &
            (config_table.c.scope == op.inline_literal('rest'))
        )
    )


def _create_usage_collector_table():
    op.create_table(
        'usage_collector',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('manager_id', sa.Text(), nullable=False),
        sa.Column('hourly_timestamp', sa.Integer(), nullable=True),
        sa.Column('daily_timestamp', sa.Integer(), nullable=True),
        sa.Column('hours_interval', sa.Integer(), nullable=False),
        sa.Column('days_interval', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('usage_collector_pkey')),
        sa.UniqueConstraint('manager_id',
                            name=op.f('usage_collector_manager_id_key'))
    )


def _drop_usage_collector_table():
    op.drop_table('usage_collector')


def _create_plugins_states_table():
    plugins_states = op.create_table(
        'plugins_states',
        sa.Column('_storage_id', sa.Integer(), autoincrement=True,
                  nullable=False),
        sa.Column('_plugin_fk', sa.Integer(), nullable=False),
        sa.Column('_manager_fk', sa.Integer(), nullable=True),
        sa.Column('_agent_fk', sa.Integer(), nullable=True),
        sa.Column('state', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ['_agent_fk'],
            ['agents._storage_id'],
            name=op.f('plugins_states__agent_fk_fkey'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_manager_fk'],
            ['managers.id'],
            name=op.f('plugins_states__manager_fk_fkey'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_plugin_fk'],
            ['plugins._storage_id'],
            name=op.f('plugins_states__plugin_fk_fkey'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint(
            '_storage_id',
            name=op.f('plugins_states_pkey'))
    )
    op.create_index(
        op.f('plugins_states__agent_fk_idx'),
        'plugins_states',
        ['_agent_fk'],
        unique=False)
    op.create_index(
        op.f('plugins_states__manager_fk_idx'),
        'plugins_states',
        ['_manager_fk'],
        unique=False)
    op.create_index(
        op.f('plugins_states__plugin_fk_idx'),
        'plugins_states',
        ['_plugin_fk'],
        unique=False)
    op.create_check_constraint(
        'plugins_states_manager_or_agent',
        'plugins_states',
        plugins_states.c._agent_fk.is_(None) !=
        plugins_states.c._manager_fk.is_(None)
    )


def _create_inter_deployment_dependencies_table():
    op.create_table(
        'inter_deployment_dependencies',
        sa.Column('_storage_id',
                  sa.Integer(),
                  autoincrement=True,
                  nullable=False),
        sa.Column('id', sa.Text(), nullable=True),
        sa.Column('visibility',
                  VISIBILITY_ENUM,
                  nullable=True),
        sa.Column('created_at',
                  storage.models_base.UTCDateTime(),
                  nullable=False),
        sa.Column('dependency_creator', sa.Text(), nullable=False),
        sa.Column('target_deployment_func', JSONString(), nullable=True),
        sa.Column('_source_deployment', sa.Integer(), nullable=True),
        sa.Column('_target_deployment', sa.Integer(), nullable=True),
        sa.Column('_tenant_id', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.Column('external_source', JSONString(), nullable=True),
        sa.Column('external_target', JSONString(), nullable=True),
        sa.ForeignKeyConstraint(
            ['_creator_id'],
            [u'users.id'],
            name=op.f('inter_deployment_dependencies__creator_id_fkey'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_source_deployment'],
            [u'deployments._storage_id'],
            name=op.f('inter_deployment_dependencies__source_deployment_fkey'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_target_deployment'],
            [u'deployments._storage_id'],
            name=op.f('inter_deployment_dependencies__target_deployment_fkey'),
            ondelete='SET NULL'),
        sa.ForeignKeyConstraint(
            ['_tenant_id'],
            [u'tenants.id'],
            name=op.f('inter_deployment_dependencies__tenant_id_fkey'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint(
            '_storage_id',
            name=op.f('inter_deployment_dependencies_pkey')),
    )
    op.create_index(op.f('inter_deployment_dependencies__tenant_id_idx'),
                    'inter_deployment_dependencies',
                    ['_tenant_id'],
                    unique=False)
    op.create_index(op.f('inter_deployment_dependencies_created_at_idx'),
                    'inter_deployment_dependencies',
                    ['created_at'],
                    unique=False)
    op.create_index(op.f('inter_deployment_dependencies_id_idx'),
                    'inter_deployment_dependencies',
                    ['id'],
                    unique=True)
    op.create_index(op.f('inter_deployment_dependencies__creator_id_idx'),
                    'inter_deployment_dependencies',
                    ['_creator_id'],
                    unique=False)
    op.create_index(op.f('inter_deployment_dependencies_visibility_idx'),
                    'inter_deployment_dependencies',
                    ['visibility'],
                    unique=False)
    op.create_index(
        op.f('inter_deployment_dependencies__source_deployment_idx'),
        'inter_deployment_dependencies',
        ['_source_deployment'],
        unique=False
    )
    op.create_index(
        op.f('inter_deployment_dependencies__target_deployment_idx'),
        'inter_deployment_dependencies',
        ['_target_deployment'],
        unique=False
    )
    op.add_column(u'deployment_updates',
                  sa.Column('keep_old_deployment_dependencies',
                            sa.Boolean(),
                            nullable=False,
                            server_default=expression.true()))


def _drop_inter_deployment_dependencies_table():
    op.drop_column(u'deployment_updates', 'keep_old_deployment_dependencies')
    op.drop_index(op.f('inter_deployment_dependencies_visibility_idx'),
                  table_name='inter_deployment_dependencies')
    op.drop_index(op.f('inter_deployment_dependencies__target_deployment_idx'),
                  table_name='inter_deployment_dependencies')
    op.drop_index(op.f('inter_deployment_dependencies__source_deployment_idx'),
                  table_name='inter_deployment_dependencies')
    op.drop_index(op.f('inter_deployment_dependencies__creator_id_idx'),
                  table_name='inter_deployment_dependencies')
    op.drop_index(op.f('inter_deployment_dependencies_id_idx'),
                  table_name='inter_deployment_dependencies')
    op.drop_index(op.f('inter_deployment_dependencies_created_at_idx'),
                  table_name='inter_deployment_dependencies')
    op.drop_index(op.f('inter_deployment_dependencies__tenant_id_idx'),
                  table_name='inter_deployment_dependencies')
    op.drop_table('inter_deployment_dependencies')


def _create_unique_indexes():
    op.create_index('blueprints_id__tenant_id_idx',
                    'blueprints',
                    ['id', '_tenant_id'],
                    unique=True)
    op.create_index('deployments__site_fk_visibility_idx',
                    'deployments',
                    ['_blueprint_fk', '_site_fk', 'visibility', '_tenant_id'],
                    unique=False)
    op.create_index('deployments_id__tenant_id_idx',
                    'deployments',
                    ['id', '_tenant_id'],
                    unique=True)
    op.drop_index('deployments__sife_fk_visibility_idx',
                  table_name='deployments')
    op.create_index('plugins_name_version__tenant_id_idx',
                    'plugins',
                    ['package_name', 'package_version', '_tenant_id',
                     'distribution', 'distribution_release',
                     'distribution_version'],
                    unique=True)
    op.create_index('secrets_id_tenant_id_idx',
                    'secrets',
                    ['id', '_tenant_id'],
                    unique=True)
    op.create_index('site_name__tenant_id_idx',
                    'sites',
                    ['name', '_tenant_id'],
                    unique=True)
    op.create_index('snapshots_id__tenant_id_idx',
                    'snapshots',
                    ['id', '_tenant_id'],
                    unique=True)
    op.drop_index('tasks_graphs__execution_fk_name_visibility_idx',
                  table_name='tasks_graphs')
    op.create_index('tasks_graphs__execution_fk_name_visibility_idx',
                    'tasks_graphs',
                    ['_execution_fk', 'name', 'visibility'],
                    unique=True)


def _drop_unique_indexes():
    op.drop_index('tasks_graphs__execution_fk_name_visibility_idx',
                  table_name='tasks_graphs')
    op.create_index('tasks_graphs__execution_fk_name_visibility_idx',
                    'tasks_graphs',
                    ['_execution_fk', 'name', 'visibility'],
                    unique=False)
    op.drop_index('snapshots_id__tenant_id_idx', table_name='snapshots')
    op.drop_index('site_name__tenant_id_idx', table_name='sites')
    op.drop_index('secrets_id_tenant_id_idx', table_name='secrets')
    op.drop_index('plugins_name_version__tenant_id_idx', table_name='plugins')
    op.create_index('deployments__sife_fk_visibility_idx',
                    'deployments',
                    ['_blueprint_fk', '_site_fk', 'visibility', '_tenant_id'],
                    unique=False)
    op.drop_index('deployments_id__tenant_id_idx', table_name='deployments')
    op.drop_index('deployments__site_fk_visibility_idx',
                  table_name='deployments')
    op.drop_index('blueprints_id__tenant_id_idx', table_name='blueprints')


def _add_plugins_title_column():
    op.add_column(u'plugins', sa.Column('title', sa.Text(), nullable=True))


def _drop_plugins_title_column():
    op.drop_column(u'plugins', 'title')


def _remove_node_id_columns():
    op.drop_constraint(u'db_nodes_node_id_key', 'db_nodes', type_='unique')
    op.drop_column('db_nodes', 'node_id')
    op.drop_constraint(u'managers_node_id_key', 'managers', type_='unique')
    op.drop_column('managers', 'node_id')
    op.drop_constraint(
        u'rabbitmq_brokers_node_id_key',
        'rabbitmq_brokers',
        type_='unique')
    op.drop_column('rabbitmq_brokers', 'node_id')


def _create_node_id_columns():
    #  The columns are added here with nullable=True. It's different from the
    #  declared table, but necessary since we can't create IDs when downgrading
    #  (and these IDs aren't gonna be used anyway after manager-update)
    op.add_column(
        u'rabbitmq_brokers',
        sa.Column('node_id', sa.TEXT(), autoincrement=False, nullable=True)
    )
    op.create_unique_constraint(
        'rabbitmq_brokers_node_id_key',
        'rabbitmq_brokers',
        ['node_id']
    )
    op.add_column(
        u'managers',
        sa.Column('node_id', sa.TEXT(), autoincrement=False, nullable=True)
    )
    op.create_unique_constraint(
        'managers_node_id_key',
        'managers',
        ['node_id']
    )
    op.add_column(
        u'db_nodes',
        sa.Column('node_id', sa.TEXT(), autoincrement=False, nullable=True)
    )
    op.create_unique_constraint(
        'db_nodes_node_id_key',
        'db_nodes',
        ['node_id']
    )


def _add_monitoring_credentials_columns():
    op.add_column(
        'db_nodes',
        sa.Column('monitoring_password', sa.Text(), nullable=True)
    )
    op.add_column(
        'db_nodes',
        sa.Column('monitoring_username', sa.Text(), nullable=True)
    )
    op.add_column(
        'managers',
        sa.Column('monitoring_password', sa.Text(), nullable=True)
    )
    op.add_column(
        'managers',
        sa.Column('monitoring_username', sa.Text(), nullable=True)
    )
    op.add_column(
        'rabbitmq_brokers',
        sa.Column('monitoring_password', sa.Text(), nullable=True)
    )
    op.add_column(
        'rabbitmq_brokers',
        sa.Column('monitoring_username', sa.Text(), nullable=True)
    )


def _remove_monitoring_credentials_columns():
    op.drop_column('rabbitmq_brokers', 'monitoring_username')
    op.drop_column('rabbitmq_brokers', 'monitoring_password')
    op.drop_column('managers', 'monitoring_username')
    op.drop_column('managers', 'monitoring_password')
    op.drop_column('db_nodes', 'monitoring_username')
    op.drop_column('db_nodes', 'monitoring_password')

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
from sqlalchemy import orm
from manager_rest import storage
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.declarative import declarative_base

from cloudify.models_states import VisibilityState

from manager_rest.storage.models import User
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

Base = declarative_base()


class Config(Base):
    __tablename__ = 'config'

    name = sa.Column(sa.Text, primary_key=True)
    value = sa.Column(JSONString(), nullable=False)
    schema = sa.Column(JSONString(), nullable=True)
    is_editable = sa.Column(sa.Boolean, default=True)
    updated_at = sa.Column(UTCDateTime())
    scope = sa.Column(sa.Text, primary_key=True)
    _updater_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(User.id, ondelete='SET NULL'),
        nullable=True,
        index=False,
        primary_key=False,
    )


def upgrade():
    _create_usage_collector_table()
    _create_inter_deployment_dependencies_table()
    _create_unique_indexes()
    _add_plugins_title_column()
    _add_service_management_column()
    _create_more_idd_indexes()
    _remove_node_id_columns()


def downgrade():
    _drop_usage_collector_table()
    _drop_inter_deployment_dependencies_table()
    _drop_unique_indexes()
    _drop_plugins_title_column()
    _drop_service_management_column()
    _drop_some_idd_indexes()
    _create_node_id_columns()


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
    op.add_column(u'deployment_updates',
                  sa.Column('keep_old_deployment_dependencies',
                            sa.Boolean(),
                            nullable=False))


def _drop_inter_deployment_dependencies_table():
    op.drop_column(u'deployment_updates', 'keep_old_deployment_dependencies')
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
                     'distribution'],
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


def _add_service_management_column():
    bind = op.get_bind()
    session = orm.Session(bind=bind)
    session.add(
        Config(
            name='service_management',
            value='systemd',
            scope='rest',
            schema=None,
            is_editable=True
        )
    )
    session.commit()


def _drop_service_management_column():
    bind = op.get_bind()
    session = orm.Session(bind=bind)
    service_management = session.query(Config).filter_by(
        name='service_management',
        scope='rest',
    ).one()
    session.delete(service_management)
    session.commit()


def _create_more_idd_indexes():
    op.create_index(
        op.f('inter_deployment_dependencies__creator_id_idx'),
        'inter_deployment_dependencies',
        ['_creator_id'],
        unique=False
    )
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
    op.create_index(
        op.f('inter_deployment_dependencies_visibility_idx'),
        'inter_deployment_dependencies',
        ['visibility'],
        unique=False
    )
    op.drop_index(
        'inter_deployment_dependencies_id_idx',
        table_name='inter_deployment_dependencies'
    )
    op.create_index(
        op.f('inter_deployment_dependencies_id_idx'),
        'inter_deployment_dependencies',
        ['id'],
        unique=False
    )


def _drop_some_idd_indexes():
    op.drop_index(
        op.f('inter_deployment_dependencies_id_idx'),
        table_name='inter_deployment_dependencies'
    )
    op.create_index(
        'inter_deployment_dependencies_id_idx',
        'inter_deployment_dependencies',
        ['id'],
        unique=True
    )
    op.drop_index(
        op.f('inter_deployment_dependencies_visibility_idx'),
        table_name='inter_deployment_dependencies'
    )
    op.drop_index(
        op.f('inter_deployment_dependencies__target_deployment_idx'),
        table_name='inter_deployment_dependencies'
    )
    op.drop_index(
        op.f('inter_deployment_dependencies__source_deployment_idx'),
        table_name='inter_deployment_dependencies'
    )
    op.drop_index(
        op.f('inter_deployment_dependencies__creator_id_idx'),
        table_name='inter_deployment_dependencies'
    )


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
    op.add_column(
        u'rabbitmq_brokers',
        sa.Column('node_id', sa.TEXT(), autoincrement=False, nullable=False)
    )
    op.create_unique_constraint(
        'rabbitmq_brokers_node_id_key',
        'rabbitmq_brokers',
        ['node_id']
    )
    op.add_column(
        u'managers',
        sa.Column('node_id', sa.TEXT(), autoincrement=False, nullable=False)
    )
    op.create_unique_constraint(
        'managers_node_id_key',
        'managers',
        ['node_id']
    )
    op.add_column(
        u'db_nodes',
        sa.Column('node_id', sa.TEXT(), autoincrement=False, nullable=False)
    )
    op.create_unique_constraint(
        'db_nodes_node_id_key',
        'db_nodes',
        ['node_id']
    )

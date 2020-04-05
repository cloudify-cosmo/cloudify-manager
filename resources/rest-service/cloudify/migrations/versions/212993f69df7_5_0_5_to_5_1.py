"""5_0_5 to 5_1

- Add usage_collector table
- Adding inter deployment dependencies table

Revision ID: 212993f69df7
Revises: 62a8d746d13b
Create Date: 2020-03-30 06:27:26.747213

"""

from alembic import op
import sqlalchemy as sa
from manager_rest import storage
from sqlalchemy.dialects import postgresql

from cloudify.models_states import VisibilityState

# revision identifiers, used by Alembic.
revision = '212993f69df7'
down_revision = '62a8d746d13b'
branch_labels = None
depends_on = None

VISIBILITY_ENUM = postgresql.ENUM(VisibilityState.PRIVATE,
                                  VisibilityState.TENANT,
                                  VisibilityState.GLOBAL,
                                  name='visibility_states',
                                  create_type=False)


def upgrade():
    _create_usage_collector_table()
    _create_inter_deployment_dependencies_table()


def downgrade():
    _drop_usage_collector_table()
    _drop_inter_deployment_dependencies_table()


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
        sa.Column('_source_deployment',
                  sa.Integer(),
                  nullable=False),
        sa.Column('_target_deployment',
                  sa.Integer(),
                  nullable=True),
        sa.Column('_tenant_id', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
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
        sa.UniqueConstraint('dependency_creator',
                            '_source_deployment',
                            '_tenant_id',
                            name='inter_deployment_uc')
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
                    unique=False)
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

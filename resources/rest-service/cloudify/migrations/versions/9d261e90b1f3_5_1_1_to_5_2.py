"""5_1_1 to 5_2

- Add columns to blueprints table for the async. blueprints upload

Revision ID: 9d261e90b1f3
Revises: 5ce2b0cbb6f3
Create Date: 2020-11-26 14:07:36.053518

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from cloudify.models_states import VisibilityState
from manager_rest.storage.models_base import JSONString, UTCDateTime

# revision identifiers, used by Alembic.
revision = '9d261e90b1f3'
down_revision = '5ce2b0cbb6f3'
branch_labels = None
depends_on = None

VISIBILITY_ENUM = postgresql.ENUM(*VisibilityState.STATES,
                                  name='visibility_states',
                                  create_type=False)


def upgrade():
    upgrade_blueprints_table()
    create_filters_table()
    create_deployment_groups_table()
    create_execution_schedules_table()


def downgrade():
    drop_deployment_groups_table()
    downgrade_blueprints_table()
    drop_filters_table()
    drop_execution_schedules_table()


def upgrade_blueprints_table():
    op.add_column('blueprints', sa.Column('state', sa.Text(), nullable=True))
    op.add_column('blueprints', sa.Column('error', sa.Text(), nullable=True))
    op.add_column('blueprints', sa.Column('error_traceback',
                                          sa.Text(),
                                          nullable=True))
    op.alter_column('blueprints', 'main_file_name',
                    existing_type=sa.TEXT(),
                    nullable=True)
    op.alter_column('blueprints', 'plan',
                    existing_type=postgresql.BYTEA(),
                    nullable=True)


def downgrade_blueprints_table():
    op.alter_column('blueprints', 'plan',
                    existing_type=postgresql.BYTEA(),
                    nullable=False)
    op.alter_column('blueprints', 'main_file_name',
                    existing_type=sa.TEXT(),
                    nullable=False)
    op.drop_column('blueprints', 'state')
    op.drop_column('blueprints', 'error')
    op.drop_column('blueprints', 'error_traceback')


def create_filters_table():
    op.create_table(
        'filters',
        sa.Column('_storage_id',
                  sa.Integer(),
                  autoincrement=True,
                  nullable=False),
        sa.Column('id', sa.Text(), nullable=True),
        sa.Column('value', JSONString(), nullable=True),
        sa.Column('visibility', VISIBILITY_ENUM, nullable=True),
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('updated_at', UTCDateTime(), nullable=True),
        sa.Column('_tenant_id', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['_creator_id'],
            [u'users.id'],
            name=op.f('filters__creator_id_fkey'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_tenant_id'],
            [u'tenants.id'],
            name=op.f('filters__tenant_id_fkey'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint(
            '_storage_id',
            name=op.f('filters_pkey')),
    )
    op.create_index(op.f('filters__tenant_id_idx'),
                    'filters',
                    ['_tenant_id'],
                    unique=False)
    op.create_index(op.f('filters_created_at_idx'),
                    'filters',
                    ['created_at'],
                    unique=False)
    op.create_index(op.f('filters_id_idx'),
                    'filters',
                    ['id'],
                    unique=True)
    op.create_index(op.f('filters__creator_id_idx'),
                    'filters',
                    ['_creator_id'],
                    unique=False)
    op.create_index(op.f('filters_visibility_idx'),
                    'filters',
                    ['visibility'],
                    unique=False)
    op.create_index(op.f('filters_value_idx'),
                    'filters',
                    ['value'],
                    unique=False)


def drop_filters_table():
    op.drop_index(op.f('filters__tenant_id_idx'),
                  table_name='filters')
    op.drop_index(op.f('filters_created_at_idx'),
                  table_name='filters')
    op.drop_index(op.f('filters_id_idx'),
                  table_name='filters')
    op.drop_index(op.f('filters__creator_id_idx'),
                  table_name='filters')
    op.drop_index(op.f('filters_visibility_idx'),
                  table_name='filters')
    op.drop_index(op.f('filters_value_idx'),
                  table_name='filters')
    op.drop_table('filters')


def create_deployment_groups_table():
    op.create_table(
        'deployment_group',
        sa.Column(
            '_storage_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id', sa.Text(), nullable=True),
        sa.Column(
            'visibility',
            postgresql.ENUM(
                'private', 'tenant', 'global', name='visibility_states',
                create_type=False),
            nullable=True
        ),
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('_default_blueprint_fk', sa.Integer(), nullable=True),
        sa.Column('default_inputs', JSONString(), nullable=True),
        sa.Column('_tenant_id', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['_default_blueprint_fk'], ['blueprints._storage_id'],
            name=op.f('deployment_group__default_blueprint_fk_fkey'),
            ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['_creator_id'], ['users.id'],
            name=op.f('deployment_group__creator_id_fkey'),
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['_tenant_id'], ['tenants.id'],
            name=op.f('deployment_group__tenant_id_fkey'),
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint(
            '_storage_id', name=op.f('deployment_group_pkey'))
    )
    op.create_index(
        op.f('deployment_group__default_blueprint_fk_idx'),
        'deployment_group',
        ['_default_blueprint_fk'],
        unique=False
    )
    op.create_index(
        op.f('deployment_group__creator_id_idx'),
        'deployment_group',
        ['_creator_id'],
        unique=False
    )
    op.create_index(
        op.f('deployment_group__tenant_id_idx'),
        'deployment_group',
        ['_tenant_id'],
        unique=False
    )
    op.create_index(
        op.f('deployment_group_created_at_idx'),
        'deployment_group',
        ['created_at'],
        unique=False
    )
    op.create_index(
        op.f('deployment_group_id_idx'),
        'deployment_group',
        ['id'],
        unique=False
    )
    op.create_index(
        op.f('deployment_group_visibility_idx'),
        'deployment_group',
        ['visibility'],
        unique=False
    )
    op.create_table(
        'deployment_group_deployments',
        sa.Column('deployment_grou_id', sa.Integer(), nullable=True),
        sa.Column('deployment_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['deployment_grou_id'],
            ['deployment_group._storage_id'],
            name=op.f('deployment_group_deployments_deployment_grou_id_fkey')
        ),
        sa.ForeignKeyConstraint(
            ['deployment_id'],
            ['deployments._storage_id'],
            name=op.f('deployment_group_deployments_deployment_id_fkey')
        )
    )


def drop_deployment_groups_table():
    op.drop_table('deployment_group_deployments')
    op.drop_index(
        op.f('deployment_group__default_blueprint_fk_idx'),
        table_name='deployment_group')
    op.drop_index(
        op.f('deployment_group_visibility_idx'), table_name='deployment_group')
    op.drop_index(
        op.f('deployment_group_id_idx'), table_name='deployment_group')
    op.drop_index(
        op.f('deployment_group_created_at_idx'), table_name='deployment_group')
    op.drop_index(
        op.f('deployment_group__tenant_id_idx'), table_name='deployment_group')
    op.drop_index(
        op.f('deployment_group__creator_id_idx'),
        table_name='deployment_group')
    op.drop_table('deployment_group')


def create_execution_schedules_table():
    op.create_table(
        'execution_schedules',
        sa.Column('_storage_id',
                  sa.Integer(),
                  autoincrement=True,
                  nullable=False),
        sa.Column('id', sa.Text(), nullable=True),
        sa.Column('visibility', VISIBILITY_ENUM, nullable=True),
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('next_occurrence', UTCDateTime(), nullable=True),
        sa.Column('since', UTCDateTime(), nullable=True),
        sa.Column('until', UTCDateTime(), nullable=True),
        sa.Column('rule', JSONString(), nullable=False),
        sa.Column('slip', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Text(), nullable=False),
        sa.Column('parameters', JSONString(), nullable=True),
        sa.Column('execution_arguments', JSONString(), nullable=True),
        sa.Column('stop_on_fail',
                  sa.Boolean(),
                  nullable=False,
                  server_default='f'),
        sa.Column('_deployment_fk', sa.Integer(), nullable=False),
        sa.Column('_latest_execution_fk', sa.Integer(), nullable=True),
        sa.Column('_tenant_id', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['_creator_id'],
            [u'users.id'],
            name=op.f('execution_schedules__creator_id_fkey'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_tenant_id'],
            [u'tenants.id'],
            name=op.f('execution_schedules__tenant_id_fkey'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_deployment_fk'],
            [u'deployments._storage_id'],
            name=op.f('execution_schedules__deployment_fkey'),
            ondelete='CASCADE'),
    )
    op.create_foreign_key(
        op.f('execution_schedules__latest_execution_fk_fkey'),
        'execution_schedules',
        'executions',
        ['_latest_execution_fk'],
        ['_storage_id'],
        ondelete='CASCADE'
    )
    op.create_index(op.f('execution_schedules_created_at_idx'),
                    'execution_schedules',
                    ['created_at'],
                    unique=False)
    op.create_index(op.f('execution_schedules_id_idx'),
                    'execution_schedules',
                    ['id'],
                    unique=False)
    op.create_index(op.f('execution_schedules__creator_id_idx'),
                    'execution_schedules',
                    ['_creator_id'],
                    unique=False)
    op.create_index(op.f('execution_schedules__tenant_id_idx'),
                    'execution_schedules',
                    ['_tenant_id'],
                    unique=False)
    op.create_index(op.f('execution_schedules_visibility_idx'),
                    'execution_schedules',
                    ['visibility'],
                    unique=False)
    op.create_index(op.f('execution_schedules_next_occurrence_idx'),
                    'execution_schedules',
                    ['next_occurrence'],
                    unique=False)
    op.create_index(op.f('execution_schedules__deployment_fk_idx'),
                    'execution_schedules',
                    ['_deployment_fk'],
                    unique=False)
    op.create_index(op.f('execution_schedules__latest_execution_fk_idx'),
                    'execution_schedules',
                    ['_latest_execution_fk'],
                    unique=False)


def drop_execution_schedules_table():
    op.drop_index(
        op.f('execution_schedules_next_occurrence_idx'),
        table_name='execution_schedules')
    op.drop_index(
        op.f('execution_schedules_visibility_idx'),
        table_name='execution_schedules')
    op.drop_index(
        op.f('execution_schedules_id_idx'),
        table_name='execution_schedules')
    op.drop_index(
        op.f('execution_schedules_created_at_idx'),
        table_name='execution_schedules')
    op.drop_index(
        op.f('execution_schedules__tenant_id_idx'),
        table_name='execution_schedules')
    op.drop_index(
        op.f('execution_schedules__creator_id_idx'),
        table_name='execution_schedules')
    op.drop_index(op.f('execution_schedules__latest_execution_fk_idx'),
                  table_name='execution_schedules')
    op.drop_index(op.f('execution_schedules__deployment_fk_idx'),
                  table_name='execution_schedules')
    op.drop_table('execution_schedules')

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

VISIBILITY_ENUM = postgresql.ENUM(VisibilityState.PRIVATE,
                                  VisibilityState.TENANT,
                                  VisibilityState.GLOBAL,
                                  name='visibility_states',
                                  create_type=False)


def upgrade():
    upgrade_blueprints_table()
    create_filters_table()


def downgrade():
    downgrade_blueprints_table()
    drop_filters_table()


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
        sa.Column('visibility',
                  VISIBILITY_ENUM,
                  nullable=True),
        sa.Column('created_at',
                  UTCDateTime(),
                  nullable=False),
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

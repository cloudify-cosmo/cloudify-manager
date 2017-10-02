"""Add role column to users_tenants table
Revision ID: 406821843b55
Revises: 3496c876cd1a
Create Date: 2017-10-01 19:37:31.484983
"""
from alembic import op
import sqlalchemy as sa
import manager_rest     # Adding this manually


# revision identifiers, used by Alembic.
revision = '406821843b55'
down_revision = '4dfd8797fdfa'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users_tenants',
        sa.Column('role_id', sa.Integer()),
    )
    op.create_foreign_key(
        'users_tenants_role_id_fkey',
        'users_tenants',
        'roles',
        ['role_id'],
        ['id'],
    )
    op.create_primary_key(
        'users_tenants_pkey',
        'users_tenants',
        ['user_id', 'tenant_id'],
    )


def downgrade():
    op.drop_constraint(
        'users_tenants_pkey',
        'users_tenants',
    )
    op.drop_constraint(
        'users_tenants_role_id_fkey',
        'users_tenants',
    )
    op.drop_column('users_tenants', 'role_id')

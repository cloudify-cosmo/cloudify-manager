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

    # Define tables with just the columns needed
    # to generate the UPDATE sql expression below
    users_tenants = sa.table(
        'users_tenants',
        sa.column('user_id', sa.Integer),
        sa.column('role_id', sa.Integer),
    )
    roles = sa.table(
        'roles',
        sa.column('id', sa.Integer),
        sa.column('name', sa.Text),
    )
    # Set 'user' role as the default for every user in a tenant
    op.execute(
        users_tenants.update()
        .values(role_id=(
            sa.select([roles.c.id])
            .where(roles.c.name == 'user')
        ))
    )
    op.alter_column('users_tenants', 'role_id', nullable=False)


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

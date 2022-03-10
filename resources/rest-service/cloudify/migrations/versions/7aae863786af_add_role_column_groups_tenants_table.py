"""Add role column to groups_tenants_table

Revision ID: 7aae863786af
Revises: 406821843b55
Create Date: 2017-10-04 11:10:48.227654

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7aae863786af'
down_revision = '406821843b55'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'groups_tenants',
        sa.Column('role_id', sa.Integer()),
    )
    op.create_foreign_key(
        'groups_tenants_role_id_fkey',
        'groups_tenants',
        'roles',
        ['role_id'],
        ['id'],
    )
    op.create_primary_key(
        'groups_tenants_pkey',
        'groups_tenants',
        ['group_id', 'tenant_id'],
    )
    # Define tables with just the columns needed
    # to generate the UPDATE sql expression below
    groups_tenants = sa.table(
        'groups_tenants',
        sa.column('group_id', sa.Integer),
        sa.column('role_id', sa.Integer),
    )
    roles = sa.table(
        'roles',
        sa.column('id', sa.Integer),
        sa.column('name', sa.Text),
    )
    # Set 'user' role as the default for every group in a tenant
    op.execute(
        groups_tenants.update()
        .values(role_id=(
            sa.select([roles.c.id])
            .where(roles.c.name == op.inline_literal('user'))
            .scalar_subquery()
        ))
    )
    op.alter_column('groups_tenants', 'role_id', nullable=False)


def downgrade():
    op.drop_constraint(
        'groups_tenants_pkey',
        'groups_tenants',
    )
    op.drop_constraint(
        'groups_tenants_role_id_fkey',
        'groups_tenants',
    )
    op.drop_column('groups_tenants', 'role_id')

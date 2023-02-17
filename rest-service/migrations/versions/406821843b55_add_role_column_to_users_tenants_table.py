"""Add role column to users_tenants table
Revision ID: 406821843b55
Revises: 3496c876cd1a
Create Date: 2017-10-01 19:37:31.484983
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '406821843b55'
down_revision = '4dfd8797fdfa'
branch_labels = None
depends_on = None

# Define tables with just the columns needed
# to generate the UPDATE sql expressions below
users_roles = sa.table(
    'users_roles',
    sa.column('user_id', sa.Integer),
    sa.column('role_id', sa.Integer),
)
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

OLD_ADMIN_ROLE_ID = 1
OLD_USER_ROLE_ID = 2


def update_system_role(from_role_id, to_role_id):
    """Helper function to update system role values.

    Calling this function will update the role for all users whose current role
    is `from_role_id` and set it to `to_role_id`.

    """
    op.execute(
        users_roles.update()
        .where(users_roles.c.role_id == op.inline_literal(from_role_id))
        .values(role_id=to_role_id)
    )


def _get_role_id(role_name):
    """
    Return a SELECT statement that retrieves a role ID from a role name
    """
    return sa.select([roles.c.id]).where(
        roles.c.name == op.inline_literal(role_name)).scalar_subquery()


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

    # Set 'user' role as the default for every user in a tenant
    op.execute(
        users_tenants.update()
        .values(role_id=_get_role_id('user'))
    )
    op.alter_column('users_tenants', 'role_id', nullable=False)

    # Manually using old role IDs, because they have changed in this version.
    # Old roles were:
    # 1 - admin
    # 2 - user
    # New roles are:
    # 1 - sys_admin
    # 2 - manager
    # 3 - user
    # 4 - viewer
    # 5 - default
    update_system_role(OLD_USER_ROLE_ID, _get_role_id('default'))
    update_system_role(OLD_ADMIN_ROLE_ID, _get_role_id('sys_admin'))


def downgrade():
    update_system_role(_get_role_id('default'), OLD_USER_ROLE_ID)
    update_system_role(_get_role_id('sys_admin'), OLD_ADMIN_ROLE_ID)

    op.drop_constraint(
        'users_tenants_pkey',
        'users_tenants',
    )
    op.drop_constraint(
        'users_tenants_role_id_fkey',
        'users_tenants',
    )
    op.drop_column('users_tenants', 'role_id')

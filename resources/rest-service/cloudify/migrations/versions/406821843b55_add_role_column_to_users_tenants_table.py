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
down_revision = '3496c876cd1a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users_tenants',
        sa.Column('role_id', sa.Integer()),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
    )


def downgrade():
    op.drop_column('users_tenants', 'role_id')

"""
4_5_5 to 4_6

- New 'Licenses' table

Revision ID: 9516df019579
Revises: 1fbd6bf39e84
Create Date: 2019-02-17 14:39:21.868748

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from manager_rest.storage.models_base import UTCDateTime

# revision identifiers, used by Alembic.
revision = '9516df019579'
down_revision = '1fbd6bf39e84'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'licenses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.Text(), nullable=True),
        sa.Column('expiration_date', UTCDateTime(), nullable=True),
        sa.Column('license_edition', sa.String(length=255), nullable=True),
        sa.Column('trial', sa.Boolean(), nullable=False),
        sa.Column('cloudify_version', sa.Text(), nullable=True),
        sa.Column('capabilities', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('signature', sa.LargeBinary(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('licenses_pkey')),
        sa.UniqueConstraint(
            'customer_id', name=op.f('licenses_customer_id_key'))
    )


def downgrade():
    op.drop_table('licenses')

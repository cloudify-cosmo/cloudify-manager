
"""
4_6 to 5_0

- Add token field to executions

Revision ID: 423a1643f365
Revises: 9516df019579
Create Date: 2019-02-21 13:00:46.042338

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import manager_rest


# revision identifiers, used by Alembic.
revision = '423a1643f365'
down_revision = '9516df019579'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('executions', sa.Column('token',
                                          sa.String(length=100),
                                          nullable=True))
    op.create_table(
        'config',
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('value', manager_rest.storage.models_base.JSONString(),
                  nullable=False),
        sa.Column('schema', manager_rest.storage.models_base.JSONString(),
                  nullable=True),
        sa.Column('updated_at', manager_rest.storage.models_base.UTCDateTime(),
                  nullable=True),
        sa.Column('is_editable', sa.Boolean(), server_default='f',
                  nullable=False),
        sa.Column('scope', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('_updater_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['_updater_id'], [u'users.id'],
                                name=op.f('config__updater_id_fkey'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('name', name=op.f('config_pkey'))
    )


def downgrade():
    op.drop_column('executions', 'token')
    op.drop_table('config')

"""Cloudify 6.3 to 6.4 DB migration

Revision ID: 272e61bf5f4a
Revises: 8e8314b1d848
Create Date: 2022-03-03 13:41:24.954542

"""
from manager_rest.storage.models_base import UTCDateTime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '272e61bf5f4a'
down_revision = '8e8314b1d848'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('tokens',
    sa.Column('created_at', UTCDateTime(), nullable=False),
    sa.Column('id', sa.String(length=10), nullable=False),
    sa.Column('secret', sa.String(length=255), nullable=False),
    sa.Column('last_used', UTCDateTime(), nullable=True),
    sa.Column('_user_fk', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['_user_fk'], ['users.id'], name=op.f('tokens__user_fk_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('tokens_pkey'))
    )
    op.create_index(op.f('tokens_last_used_idx'), 'tokens', ['last_used'], unique=False)
    op.create_index(op.f('tokens_created_at_idx'), 'tokens', ['created_at'], unique=False)
    op.create_index(op.f('tokens_id_idx'), 'tokens', ['id'], unique=True)


def downgrade():
    op.drop_index(op.f('tokens_last_used_idx'), table_name='tokens')
    op.drop_index(op.f('tokens_id_idx'), table_name='tokens')
    op.drop_index(op.f('tokens_created_at_idx'), table_name='tokens')
    op.drop_table('tokens')

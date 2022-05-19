"""empty message

Revision ID: a2609b747f8a
Revises: 272e61bf5f4a
Create Date: 2022-05-19 13:35:45.554132

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2609b747f8a'
down_revision = '272e61bf5f4a'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('users', 'api_token_key')
    op.drop_index('tokens_id_idx', table_name='tokens')


def downgrade():
    op.add_column('users', sa.Column('api_token_key', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
    op.create_index('tokens_id_idx', 'tokens', ['id'], unique=False)

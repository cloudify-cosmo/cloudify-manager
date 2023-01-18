"""Drop server-side event timestamp defaults

Revision ID: 3496c876cd1a
Revises: 730403566523
Create Date: 2017-06-20 10:58:39.408846

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3496c876cd1a'
down_revision = '730403566523'
branch_labels = None
depends_on = None


def upgrade():
    for table_name in ['events', 'logs']:
        op.alter_column(
            table_name,
            'timestamp',
            server_default=None,
            nullable=False,
        ),


def downgrade():
    for table_name in ['events', 'logs']:
        op.alter_column(
            table_name,
            'timestamp',
            server_default=sa.func.current_timestamp(),
            nullable=False,
        )

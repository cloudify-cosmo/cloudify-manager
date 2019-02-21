
"""
4_6 to 5_0

- Add token field to executions

Revision ID: 423a1643f365
Revises: 9516df019579
Create Date: 2019-02-21 13:00:46.042338

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '423a1643f365'
down_revision = '9516df019579'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('executions', sa.Column('token',
                                          sa.String(length=100),
                                          nullable=True))


def downgrade():
    op.drop_column('executions', 'token')

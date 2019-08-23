"""
5_0 to 5_0_5


Revision ID: 62a8d746d13b
Revises: 423a1643f365
Create Date: 2019-08-23 13:36:03.985636

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '62a8d746d13b'
down_revision = '423a1643f365'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('executions', sa.Column('blueprint_id', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('executions', 'blueprint_id')

"""5_1 to 5_1_1

- Add column topology_order to deployment_update_steps table

Revision ID: 5ce2b0cbb6f3
Revises: 387fcd049efb
Create Date: 2020-11-09 15:12:12.055532

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5ce2b0cbb6f3'
down_revision = '387fcd049efb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'deployment_update_steps',
        sa.Column('topology_order', sa.Integer(), nullable=False))


def downgrade():
    op.drop_column('deployment_update_steps', 'topology_order')

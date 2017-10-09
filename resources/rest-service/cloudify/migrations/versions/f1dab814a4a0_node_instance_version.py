"""Make node instance's version column not nullable

Revision ID: f1dab814a4a0
Revises: 7aae863786af
Create Date: 2017-10-08 12:59:58.047124

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1dab814a4a0'
down_revision = '7aae863786af'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('node_instances', 'version',
                    existing_type=sa.INTEGER(),
                    nullable=False)


def downgrade():
    op.alter_column('node_instances', 'version',
                    existing_type=sa.INTEGER(),
                    nullable=True)

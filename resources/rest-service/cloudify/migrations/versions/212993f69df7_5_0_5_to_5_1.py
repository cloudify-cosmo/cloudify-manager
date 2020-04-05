"""
5_0_5 to 5_1

- Add usage_collector table

Revision ID: 212993f69df7
Revises: 62a8d746d13b
Create Date: 2020-03-30 06:27:26.747213

"""
from alembic import op
import sqlalchemy as sa

revision = '212993f69df7'
down_revision = '62a8d746d13b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'usage_collector',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('manager_id', sa.Text(), nullable=False),
        sa.Column('hourly_timestamp', sa.Integer(), nullable=True),
        sa.Column('daily_timestamp', sa.Integer(), nullable=True),
        sa.Column('hours_interval', sa.Integer(), nullable=False),
        sa.Column('days_interval', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('usage_collector_pkey')),
        sa.UniqueConstraint('manager_id',
                            name=op.f('usage_collector_manager_id_key'))
    )


def downgrade():
    op.drop_table('usage_collector')

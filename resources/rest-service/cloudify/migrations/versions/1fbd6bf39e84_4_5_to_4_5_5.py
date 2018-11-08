"""4.5 to 4.5.5
 - Add dry_run indication in executions table
 - Add capabilities field to deployments
 - Add source/target nodes instance IDs to events and logs

Revision ID: 1fbd6bf39e84
Revises: a6d00b128933
Create Date: 2018-10-07 06:31:52.955877

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1fbd6bf39e84'
down_revision = 'a6d00b128933'
branch_labels = None
depends_on = None


def upgrade():
    # server_default accepts string or SQL element only
    op.add_column('executions', sa.Column('is_dry_run',
                                          sa.Boolean(),
                                          nullable=False,
                                          server_default='f'))

    op.add_column(
        'deployments',
        sa.Column('capabilities', sa.PickleType(comparator=lambda *a: False))
    )
    op.add_column('events', sa.Column('source_id', sa.Text(), nullable=True))
    op.add_column('events', sa.Column('target_id', sa.Text(), nullable=True))
    op.add_column('logs', sa.Column('source_id', sa.Text(), nullable=True))
    op.add_column('logs', sa.Column('target_id', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('executions', 'is_dry_run')
    op.drop_column('deployments', 'capabilities')
    op.drop_column('events', 'source_id')
    op.drop_column('events', 'target_id')
    op.drop_column('logs', 'source_id')
    op.drop_column('logs', 'target_id')

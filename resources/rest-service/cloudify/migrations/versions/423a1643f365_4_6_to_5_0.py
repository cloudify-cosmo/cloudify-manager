
"""
4_6 to 5_0

- Add token field to executions
- Change the id field to not nullable in all the SQLResourceBase tables

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

resource_tables = ['blueprints', 'plugins', 'secrets', 'snapshots', 'nodes',
                   'executions', 'deployment_modifications', 'node_instances',
                   'deployments', 'deployment_updates', 'tasks_graphs',
                   'deployment_update_steps', 'operations']


def upgrade():
    # Add the token field to executions
    op.add_column('executions', sa.Column('token',
                                          sa.String(length=100),
                                          nullable=True))

    # Remove the id field from logs and events (wasn't in use)
    op.drop_index('events_id_idx', table_name='events')
    op.drop_column('events', 'id')
    op.drop_index('logs_id_idx', table_name='logs')
    op.drop_column('logs', 'id')

    # Change the id field to not nullable in all the SQLResourceBase tables
    for table_name in resource_tables:
        op.alter_column(table_name,
                        'id',
                        existing_type=sa.TEXT(),
                        nullable=False)


def downgrade():
    # Drop the token field
    op.drop_column('executions', 'token')

    # Add the id field to logs and events
    op.add_column('logs', sa.Column('id', sa.TEXT(), autoincrement=False,
                                    nullable=True))
    op.create_index('logs_id_idx', 'logs', ['id'], unique=False)
    op.add_column('events', sa.Column('id', sa.TEXT(), autoincrement=False,
                                      nullable=True))
    op.create_index('events_id_idx', 'events', ['id'], unique=False)

    # Change back the id field to nullable in all the SQLResourceBase tables
    for table_name in resource_tables:
        op.alter_column(table_name,
                        'id',
                        existing_type=sa.TEXT(),
                        nullable=True)

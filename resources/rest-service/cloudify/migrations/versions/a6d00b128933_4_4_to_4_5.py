"""4_4_to_4_5

Revision ID: a6d00b128933
Revises: c7652b2a97a4
Create Date: 2018-08-05 09:05:15.625382

"""
from alembic import op
import sqlalchemy as sa
from manager_rest.storage.models_base import UTCDateTime


# revision identifiers, used by Alembic.
revision = 'a6d00b128933'
down_revision = 'c7652b2a97a4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('executions', sa.Column('started_at',
                                          UTCDateTime(),
                                          nullable=True))

    op.execute('COMMIT')

    # Add new execution status
    op.execute("alter type execution_status add value 'queued'")

    op.create_index(
        op.f('events__execution_fk_idx'),
        'events',
        ['_execution_fk'],
        unique=False)
    op.create_index(
        op.f('logs__execution_fk_idx'),
        'logs',
        ['_execution_fk'],
        unique=False)


def downgrade():
    op.drop_column('executions', 'started_at')

    # remove the 'queued' value of the execution status enum.
    # Since we are downgrading, and in older versions the `queue` option does
    # not exist, we change it to `failed`.
    op.execute("""
      update executions
      set status='failed'
      where status='queued'
      """)

    # unfortunately postgres doesn't directly support removing enum values,
    # so we create a new type with the correct enum values and swap
    # out the old one
    op.execute("alter type execution_status rename to execution_status_old")

    # create the new type
    execution_status = sa.Enum(
        'terminated',
        'failed',
        'cancelled',
        'pending',
        'started',
        'cancelling',
        'force_cancelling',
        'kill_cancelling',
        name='execution_status',
    )
    execution_status.create(op.get_bind())

    # update executions to use the new type
    op.alter_column('executions',
                    'status',
                    type_=execution_status,
                    postgresql_using='status::text::execution_status')

    # remove the old type
    op.execute("DROP TYPE execution_status_old;")

    op.drop_index(op.f('logs__execution_fk_idx'), table_name='logs')
    op.drop_index(op.f('events__execution_fk_idx'), table_name='events')

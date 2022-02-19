"""4.3 to 4.4 - add is_hidden_value column to secrets table

Revision ID: c7652b2a97a4
Revises: 3483e421713d
Create Date: 2018-04-03 14:31:11.832546

"""
from alembic import op
import sqlalchemy as sa
from manager_rest.storage.models_base import UTCDateTime

# revision identifiers, used by Alembic.
revision = 'c7652b2a97a4'
down_revision = '3483e421713d'
branch_labels = None
depends_on = None


def upgrade():
    # server_default accepts string or SQL element only
    op.add_column('secrets', sa.Column('is_hidden_value',
                                       sa.Boolean(),
                                       nullable=False,
                                       server_default='f'))
    op.add_column('deployment_updates', sa.Column('_old_blueprint_fk',
                                                  sa.Integer(),
                                                  nullable=True))
    op.add_column('deployment_updates', sa.Column('_new_blueprint_fk',
                                                  sa.Integer(),
                                                  nullable=True))
    op.add_column('deployment_updates', sa.Column('old_inputs',
                                                  sa.PickleType(),
                                                  nullable=True))
    op.add_column('deployment_updates', sa.Column('new_inputs',
                                                  sa.PickleType(),
                                                  nullable=True))
    op.add_column('users', sa.Column('last_failed_login_at',
                                     UTCDateTime(),
                                     nullable=True))
    op.add_column('users', sa.Column('failed_logins_counter',
                                     sa.Integer(),
                                     nullable=False,
                                     server_default="0"))
    op.add_column('executions', sa.Column('ended_at',
                                          UTCDateTime(),
                                          nullable=True))
    op.execute("alter type execution_status add value 'kill_cancelling'")


def downgrade():
    op.drop_column('secrets', 'is_hidden_value')
    op.drop_column('deployment_updates', '_old_blueprint_fk')
    op.drop_column('deployment_updates', '_new_blueprint_fk')
    op.drop_column('deployment_updates', 'old_inputs')
    op.drop_column('deployment_updates', 'new_inputs')
    op.drop_column('users', 'last_failed_login_at')
    op.drop_column('users', 'failed_logins_counter')
    op.drop_column('executions', 'ended_at')

    # remove the 'kill_cancelling' value of the execution status enum
    # we are downgrading, so first change the executions that are currently
    # kill_cancelling to something else that makes sense. It might well be
    # failed, since during downgrade, mgmtworker is surely not running.
    op.execute("""
      update executions
      set status='failed'
      where status='kill_cancelling'
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

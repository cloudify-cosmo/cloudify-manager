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
from sqlalchemy.dialects import postgresql

from cloudify.models_states import AgentState, VisibilityState

# Adding this manually
import manager_rest


# revision identifiers, used by Alembic.
revision = '1fbd6bf39e84'
down_revision = 'a6d00b128933'
branch_labels = None
depends_on = None

resource_tables = ['blueprints', 'plugins', 'secrets', 'snapshots', 'events',
                   'executions', 'logs', 'nodes', 'node_instances',
                   'deployments', 'deployment_modifications',
                   'deployment_updates', 'deployment_update_steps']


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

    # Create the agents table
    visibility_enum = postgresql.ENUM(*VisibilityState.STATES,
                                      name='visibility_states',
                                      create_type=False)
    agent_states_enum = postgresql.ENUM(*AgentState.STATES,
                                        name='agent_states')
    utc_datetime = manager_rest.storage.models_base.UTCDateTime()
    op.create_table(
        'agents',
        sa.Column('_storage_id', sa.Integer(), nullable=False),
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('ip', sa.Text(), nullable=True),
        sa.Column('install_method', sa.Text(), nullable=False),
        sa.Column('system', sa.Text(), nullable=True),
        sa.Column('version', sa.Text(), nullable=False),
        sa.Column('state', agent_states_enum, nullable=False),
        sa.Column('visibility', visibility_enum, nullable=True),
        sa.Column('rabbitmq_username', sa.Text(), nullable=True),
        sa.Column('rabbitmq_password', sa.Text(), nullable=True),
        sa.Column('rabbitmq_exchange', sa.Text(), nullable=False),
        sa.Column('created_at', utc_datetime, nullable=False),
        sa.Column('updated_at', utc_datetime, nullable=True),
        sa.Column('_node_instance_fk', sa.Integer(), nullable=False),
        sa.Column('_tenant_id', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['_creator_id'],
            [u'users.id'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['_node_instance_fk'],
            [u'node_instances._storage_id'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['_tenant_id'],
            [u'tenants.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('_storage_id')
    )
    op.create_index(
        op.f('agents__tenant_id_idx'),
        'agents',
        ['_tenant_id'],
        unique=False)
    op.create_index(
        op.f('agents_created_at_idx'),
        'agents',
        ['created_at'],
        unique=False
    )
    op.create_index(
        op.f('agents_id_idx'),
        'agents',
        ['id'],
        unique=False
    )

    # Remove the deprecated column private_resource from all the
    # resources tables
    for table_name in resource_tables:
        op.drop_column(table_name, 'private_resource')


def downgrade():
    op.drop_column('executions', 'is_dry_run')
    op.drop_column('deployments', 'capabilities')
    op.drop_column('events', 'source_id')
    op.drop_column('events', 'target_id')
    op.drop_column('logs', 'source_id')
    op.drop_column('logs', 'target_id')

    # Remove the agents table
    op.drop_index(op.f('agents_id_idx'), table_name='agents')
    op.drop_index(op.f('agents_created_at_idx'), table_name='agents')
    op.drop_index(op.f('agents__tenant_id_idx'), table_name='agents')
    op.drop_table('agents')
    op.execute("DROP TYPE agent_states;")

    # Add the private_resource column to all resources tables
    for table_name in resource_tables:
        op.add_column(
            table_name,
            sa.Column('private_resource', sa.Boolean(), nullable=True)
        )

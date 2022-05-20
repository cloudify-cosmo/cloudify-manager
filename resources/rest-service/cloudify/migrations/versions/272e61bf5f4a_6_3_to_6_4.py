"""Cloudify 6.3 to 6.4 DB migration

Revision ID: 272e61bf5f4a
Revises: 8e8314b1d848
Create Date: 2022-03-03 13:41:24.954542

"""
from manager_rest.storage.models_base import JSONString, UTCDateTime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '272e61bf5f4a'
down_revision = '8e8314b1d848'
branch_labels = None
depends_on = None


def upgrade():
    create_tokens()
    upgrade_plugin_updates()
    drop_usagecollector_audit()
    add_manager_agent_name_columns()
    create_log_bundles()


def downgrade():
    drop_tokens()
    downgrade_plugin_updates()
    recreate_usagecollector_audit()
    drop_manager_agent_name_columns()
    drop_log_bundles()


def create_log_bundles():
    op.create_table(
        'log_bundles',
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('_storage_id', sa.Integer(), autoincrement=True,
                  nullable=False),
        sa.Column('id', sa.Text(), nullable=True),
        sa.Column('visibility',
                  sa.Enum('private', 'tenant', 'global',
                          name='visibility_states'),
                  nullable=True),
        sa.Column('status',
                  sa.Enum('created', 'failed', 'creating', 'uploaded',
                          name='log_bundle_status'),
                  nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('_tenant_id', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['_creator_id'], ['users.id'],
                                name=op.f('log_bundles__creator_id_fkey'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['_tenant_id'], ['tenants.id'],
                                name=op.f('log_bundles__tenant_id_fkey'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('_storage_id', name=op.f('log_bundles_pkey'))
    )
    op.create_index(op.f('log_bundles__creator_id_idx'), 'log_bundles',
                    ['_creator_id'], unique=False)
    op.create_index(op.f('log_bundles__tenant_id_idx'), 'log_bundles',
                    ['_tenant_id'], unique=False)
    op.create_index(op.f('log_bundles_created_at_idx'), 'log_bundles',
                    ['created_at'], unique=False)
    op.create_index('log_bundles_id__tenant_id_idx', 'log_bundles',
                    ['id', '_tenant_id'], unique=True)
    op.create_index(op.f('log_bundles_id_idx'), 'log_bundles',
                    ['id'], unique=False)
    op.create_index(op.f('log_bundles_visibility_idx'), 'log_bundles',
                    ['visibility'], unique=False)


def drop_log_bundles():
    op.drop_table('log_bundles')


def create_tokens():
    op.create_table(
        'tokens',
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('id', sa.String(length=10), nullable=False),
        sa.Column('secret_hash', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('last_used', UTCDateTime(), nullable=True),
        sa.Column('expiration_date', UTCDateTime(), nullable=True),
        sa.Column('_user_fk', sa.Integer(), nullable=False),
        sa.Column('_execution_fk', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['_user_fk'], ['users.id'],
            name=op.f('tokens__user_fk_fkey'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_execution_fk'], ['executions._storage_id'],
            name=op.f('tokens__execution_fk_fkey'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('tokens_pkey'))
    )
    op.create_index(op.f('tokens_last_used_idx'),
                    'tokens', ['last_used'], unique=False)
    op.create_index(op.f('tokens__execution_fk_idx'),
                    'tokens', ['_execution_fk'], unique=False)
    op.create_index(op.f('tokens__user_fk_idx'),
                    'tokens', ['_user_fk'], unique=False)
    op.create_index(op.f('tokens_created_at_idx'),
                    'tokens', ['created_at'], unique=False)
    op.drop_column('users', 'api_token_key')


def drop_tokens():
    op.drop_table('tokens')
    op.add_column('users', sa.Column('api_token_key', sa.VARCHAR(length=100),
                  autoincrement=False, nullable=True))


def upgrade_plugin_updates():
    op.add_column(
        'plugins_updates',
        sa.Column('deployments_per_tenant', JSONString())
    )
    op.add_column(
        'plugins_updates',
        sa.Column('all_tenants', sa.Boolean,
                  nullable=False, server_default='f')
    )


def downgrade_plugin_updates():
    op.drop_column('plugins_updates', 'all_tenants')
    op.drop_column('plugins_updates', 'deployments_per_tenant')


def drop_usagecollector_audit():
    op.execute("""
        DROP TRIGGER IF EXISTS audit_usage_collector ON usage_collector;
    """)


def recreate_usagecollector_audit():
    op.execute("""
        CREATE TRIGGER audit_usage_collector
        AFTER INSERT OR UPDATE OR DELETE ON usage_collector FOR EACH ROW
        EXECUTE PROCEDURE write_audit_log_id('usage_collector');
    """)


def add_manager_agent_name_columns():
    op.add_column(
        'operations', sa.Column('manager_name', sa.Text(), nullable=True))
    op.add_column(
        'operations', sa.Column('agent_name', sa.Text(), nullable=True))
    op.add_column(
        'events', sa.Column('manager_name', sa.Text(), nullable=True))
    op.add_column('events', sa.Column('agent_name', sa.Text(), nullable=True))
    op.add_column('logs', sa.Column('manager_name', sa.Text(), nullable=True))
    op.add_column('logs', sa.Column('agent_name', sa.Text(), nullable=True))


def drop_manager_agent_name_columns():
    op.drop_column('operations', 'agent_name')
    op.drop_column('operations', 'manager_name')
    op.drop_column('events', 'agent_name')
    op.drop_column('events', 'manager_name')
    op.drop_column('logs', 'agent_name')
    op.drop_column('logs', 'manager_name')

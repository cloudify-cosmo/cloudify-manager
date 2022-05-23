"""Cloudify 6.3 to 6.4 DB migration

Revision ID: 272e61bf5f4a
Revises: 8e8314b1d848
Create Date: 2022-03-03 13:41:24.954542

"""
from manager_rest.storage.models_base import JSONString, UTCDateTime
from cloudify.models_states import VisibilityState
from sqlalchemy.dialects import postgresql

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '272e61bf5f4a'
down_revision = '8e8314b1d848'
branch_labels = None
depends_on = None

VISIBILITY_ENUM = postgresql.ENUM(VisibilityState.PRIVATE,
                                  VisibilityState.TENANT,
                                  VisibilityState.GLOBAL,
                                  name='visibility_states',
                                  create_type=False)

config_table = sa.table(
    'config',
    sa.Column('name', sa.Text),
    sa.Column('value', JSONString()),
    sa.Column('schema', JSONString()),
    sa.Column('is_editable', sa.Boolean),
    sa.Column('admin_only', sa.Boolean),
    sa.Column('updated_at', UTCDateTime()),
    sa.Column('scope', sa.Text),
)


def upgrade():
    depup_steps_entity_id_to_array()
    create_tokens()
    upgrade_plugin_updates()
    drop_usagecollector_audit()
    add_manager_agent_name_columns()
    create_log_bundles()
    drop_old_monitoring_cred_fields()
    add_config_admin_only_column()
    add_config_log_fetch_credentials()


def downgrade():
    depup_steps_entity_id_to_text()
    drop_tokens()
    downgrade_plugin_updates()
    recreate_usagecollector_audit()
    drop_manager_agent_name_columns()
    drop_log_bundles()
    create_old_monitoring_cred_fields()
    drop_config_admin_only_column()
    drop_config_log_fetch_credentials()


def add_config_log_fetch_credentials():
    op.bulk_insert(
        config_table,
        [
            {
                'name': 'log_fetch_username',
                'value': None,
                'scope': 'rest',
                'schema': None,
                'is_editable': True,
                'admin_only': True,
            },
            {
                'name': 'log_fetch_password',
                'value': None,
                'scope': 'rest',
                'schema': None,
                'is_editable': True,
                'admin_only': True,
            },
        ]
    )


def drop_config_log_fetch_credentials():
    for key in ['log_fetch_username', 'log_fetch_password']:
        op.execute(
            config_table
            .delete()
            .where(
                (config_table.c.name == op.inline_literal(key))
                & (config_table.c.scope == op.inline_literal('rest'))
            )
        )


def drop_old_monitoring_cred_fields():
    op.drop_column('db_nodes', 'monitoring_username')
    op.drop_column('db_nodes', 'monitoring_password')
    op.drop_column('managers', 'monitoring_password')
    op.drop_column('managers', 'monitoring_username')
    op.drop_column('rabbitmq_brokers', 'monitoring_password')
    op.drop_column('rabbitmq_brokers', 'monitoring_username')


def create_old_monitoring_cred_fields():
    op.add_column('rabbitmq_brokers',
                  sa.Column('monitoring_username', sa.TEXT(),
                            autoincrement=False, nullable=True))
    op.add_column('rabbitmq_brokers',
                  sa.Column('monitoring_password', sa.TEXT(),
                            autoincrement=False, nullable=True))
    op.add_column('managers',
                  sa.Column('monitoring_username', sa.TEXT(),
                            autoincrement=False, nullable=True))
    op.add_column('managers',
                  sa.Column('monitoring_password', sa.TEXT(),
                            autoincrement=False, nullable=True))
    op.add_column('db_nodes',
                  sa.Column('monitoring_password', sa.TEXT(),
                            autoincrement=False, nullable=True))
    op.add_column('db_nodes',
                  sa.Column('monitoring_username', sa.TEXT(),
                            autoincrement=False, nullable=True))


def create_log_bundles():
    op.create_table(
        'log_bundles',
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('_storage_id', sa.Integer(), autoincrement=True,
                  nullable=False),
        sa.Column('id', sa.Text(), nullable=True),
        sa.Column('visibility', VISIBILITY_ENUM, nullable=True),
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
    op.execute('DROP TYPE log_bundle_status;')


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


def depup_steps_entity_id_to_array():
    op.alter_column('deployment_update_steps',
                    column_name='entity_id',
                    type_=postgresql.ARRAY(sa.Text()),
                    postgresql_using="string_to_array(entity_id, ':')")


def depup_steps_entity_id_to_text():
    op.alter_column('deployment_update_steps',
                    column_name='entity_id',
                    type_=sa.Text(),
                    postgresql_using="array_to_string(entity_id, ':')")


def add_config_admin_only_column():
    op.add_column(
        'config',
        sa.Column('admin_only', sa.Boolean(),
                  server_default='false', nullable=False)
    )
    for key in [
        'ldap_username',
        'ldap_password',
    ]:
        op.execute(
            config_table
            .update()
            .where(config_table.c.name == op.inline_literal(key))
            .values(admin_only=True)
        )


def drop_config_admin_only_column():
    op.drop_column('config', 'admin_only')

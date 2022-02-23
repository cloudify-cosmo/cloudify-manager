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
    op.add_column('executions',
                  sa.Column('started_at', UTCDateTime(), nullable=True))

    with op.get_context().autocommit_block():
        # Add new execution status
        op.execute("alter type execution_status add value 'queued'")

    # add execution_fk index to logs and events
    op.create_index(
        op.f('events__execution_fk_idx'),
        'events', ['_execution_fk'],
        unique=False)
    op.create_index(
        op.f('logs__execution_fk_idx'),
        'logs', ['_execution_fk'],
        unique=False)

    # re-make FKs with ondelete=cascade
    op.drop_constraint(
        u'groups_tenants_group_id_fkey', 'groups_tenants', type_='foreignkey')
    op.drop_constraint(
        u'groups_tenants_tenant_id_fkey', 'groups_tenants', type_='foreignkey')
    op.drop_constraint(
        u'groups_tenants_role_id_fkey', 'groups_tenants', type_='foreignkey')
    op.create_foreign_key(
        op.f('groups_tenants_tenant_id_fkey'),
        'groups_tenants',
        'tenants', ['tenant_id'], ['id'],
        ondelete='CASCADE')
    op.create_foreign_key(
        op.f('groups_tenants_group_id_fkey'),
        'groups_tenants',
        'groups', ['group_id'], ['id'],
        ondelete='CASCADE')
    op.create_foreign_key(
        op.f('groups_tenants_role_id_fkey'),
        'groups_tenants',
        'roles', ['role_id'], ['id'],
        ondelete='CASCADE')

    op.drop_constraint(
        u'users_tenants_user_id_fkey', 'users_tenants', type_='foreignkey')
    op.drop_constraint(
        u'users_tenants_tenant_id_fkey', 'users_tenants', type_='foreignkey')
    op.drop_constraint(
        u'users_tenants_role_id_fkey', 'users_tenants', type_='foreignkey')
    op.create_foreign_key(
        op.f('users_tenants_tenant_id_fkey'),
        'users_tenants',
        'tenants', ['tenant_id'], ['id'],
        ondelete='CASCADE')
    op.create_foreign_key(
        op.f('users_tenants_user_id_fkey'),
        'users_tenants',
        'users', ['user_id'], ['id'],
        ondelete='CASCADE')
    op.create_foreign_key(
        op.f('users_tenants_role_id_fkey'),
        'users_tenants',
        'roles', ['role_id'], ['id'],
        ondelete='CASCADE')

    # set null=true
    op.alter_column(
        'groups_tenants', 'role_id', existing_type=sa.INTEGER(), nullable=True)

    # dep_up blueprint fks
    op.create_foreign_key(
        op.f('deployment_updates__old_blueprint_fk_fkey'),
        'deployment_updates',
        'blueprints', ['_old_blueprint_fk'], ['_storage_id'],
        ondelete='CASCADE')
    op.create_foreign_key(
        op.f('deployment_updates__new_blueprint_fk_fkey'),
        'deployment_updates',
        'blueprints', ['_new_blueprint_fk'], ['_storage_id'],
        ondelete='CASCADE')

    # adding tenant_id indexes
    op.create_index(
        op.f('blueprints__tenant_id_idx'),
        'blueprints', ['_tenant_id'],
        unique=False)
    op.create_index(
        op.f('deployment_modifications__tenant_id_idx'),
        'deployment_modifications', ['_tenant_id'],
        unique=False)
    op.create_index(
        op.f('deployment_update_steps__tenant_id_idx'),
        'deployment_update_steps', ['_tenant_id'],
        unique=False)
    op.create_index(
        op.f('deployment_updates__tenant_id_idx'),
        'deployment_updates', ['_tenant_id'],
        unique=False)
    op.create_index(
        op.f('deployments__tenant_id_idx'),
        'deployments', ['_tenant_id'],
        unique=False)
    op.create_index(
        op.f('events__tenant_id_idx'), 'events', ['_tenant_id'], unique=False)
    op.create_index(
        op.f('executions__tenant_id_idx'),
        'executions', ['_tenant_id'],
        unique=False)
    op.create_index(
        op.f('logs__tenant_id_idx'), 'logs', ['_tenant_id'], unique=False)
    op.create_index(
        op.f('nodes__tenant_id_idx'), 'nodes', ['_tenant_id'], unique=False)
    op.create_index(
        op.f('node_instances__tenant_id_idx'),
        'node_instances', ['_tenant_id'],
        unique=False)
    op.create_index(
        op.f('plugins__tenant_id_idx'),
        'plugins', ['_tenant_id'],
        unique=False)
    op.create_index(
        op.f('snapshots__tenant_id_idx'),
        'snapshots', ['_tenant_id'],
        unique=False)
    op.create_index(
        op.f('secrets__tenant_id_idx'),
        'secrets', ['_tenant_id'],
        unique=False)

    # removing duplicated indexes
    op.drop_index('ix_blueprints_created_at', table_name='blueprints')
    op.drop_index('ix_blueprints_id', table_name='blueprints')

    op.drop_index(
        'ix_deployment_modifications_created_at',
        table_name='deployment_modifications')
    op.drop_index(
        'ix_deployment_modifications_ended_at',
        table_name='deployment_modifications')
    op.drop_index(
        'ix_deployment_modifications_id',
        table_name='deployment_modifications')

    op.drop_index(
        'ix_deployment_update_steps_id', table_name='deployment_update_steps')
    op.drop_index(
        'ix_deployment_updates_created_at', table_name='deployment_updates')
    op.drop_index('ix_deployment_updates_id', table_name='deployment_updates')

    op.drop_index('ix_deployments_created_at', table_name='deployments')
    op.drop_index('ix_deployments_id', table_name='deployments')

    op.drop_index('ix_events_id', table_name='events')
    op.drop_index('ix_logs_id', table_name='logs')

    op.drop_index('ix_executions_created_at', table_name='executions')
    op.drop_index('ix_executions_id', table_name='executions')

    op.drop_index('ix_groups_ldap_dn', table_name='groups')
    op.drop_index('ix_groups_name', table_name='groups')

    op.drop_index('ix_node_instances_id', table_name='node_instances')

    op.drop_index('ix_nodes_id', table_name='nodes')
    op.drop_index('ix_nodes_type', table_name='nodes')

    op.drop_index('ix_plugins_archive_name', table_name='plugins')
    op.drop_index('ix_plugins_id', table_name='plugins')
    op.drop_index('ix_plugins_package_name', table_name='plugins')
    op.drop_index('ix_plugins_uploaded_at', table_name='plugins')

    op.drop_index('ix_secrets_created_at', table_name='secrets')
    op.drop_index('ix_secrets_id', table_name='secrets')

    op.drop_index('ix_snapshots_created_at', table_name='snapshots')
    op.drop_index('ix_snapshots_id', table_name='snapshots')

    op.drop_index('ix_tenants_name', table_name='tenants')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_roles_name', table_name='roles')


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
    op.alter_column(
        'executions',
        'status',
        type_=execution_status,
        postgresql_using='status::text::execution_status')

    # remove the old type
    op.execute("DROP TYPE execution_status_old;")

    op.drop_index(op.f('logs__execution_fk_idx'), table_name='logs')
    op.drop_index(op.f('events__execution_fk_idx'), table_name='events')

    # re-make FKs without ondelete=cascade
    op.drop_constraint(
        op.f('users_tenants_role_id_fkey'),
        'users_tenants',
        type_='foreignkey')
    op.drop_constraint(
        op.f('users_tenants_user_id_fkey'),
        'users_tenants',
        type_='foreignkey')
    op.drop_constraint(
        op.f('users_tenants_tenant_id_fkey'),
        'users_tenants',
        type_='foreignkey')
    op.create_foreign_key(u'users_tenants_role_id_fkey', 'users_tenants',
                          'roles', ['role_id'], ['id'])
    op.create_foreign_key(u'users_tenants_tenant_id_fkey', 'users_tenants',
                          'tenants', ['tenant_id'], ['id'])
    op.create_foreign_key(u'users_tenants_user_id_fkey', 'users_tenants',
                          'users', ['user_id'], ['id'])

    op.drop_constraint(
        op.f('groups_tenants_role_id_fkey'),
        'groups_tenants',
        type_='foreignkey')
    op.drop_constraint(
        op.f('groups_tenants_group_id_fkey'),
        'groups_tenants',
        type_='foreignkey')
    op.drop_constraint(
        op.f('groups_tenants_tenant_id_fkey'),
        'groups_tenants',
        type_='foreignkey')
    op.create_foreign_key(u'groups_tenants_role_id_fkey', 'groups_tenants',
                          'roles', ['role_id'], ['id'])
    op.create_foreign_key(u'groups_tenants_tenant_id_fkey', 'groups_tenants',
                          'tenants', ['tenant_id'], ['id'])
    op.create_foreign_key(u'groups_tenants_group_id_fkey', 'groups_tenants',
                          'groups', ['group_id'], ['id'])

    # set null=false
    op.alter_column(
        'groups_tenants',
        'role_id',
        existing_type=sa.INTEGER(),
        nullable=False)

    # dep_up blueprint fks
    op.drop_constraint(
        op.f('deployment_updates__new_blueprint_fk_fkey'),
        'deployment_updates',
        type_='foreignkey')
    op.drop_constraint(
        op.f('deployment_updates__old_blueprint_fk_fkey'),
        'deployment_updates',
        type_='foreignkey')

    # tenant_id indexes
    op.drop_index(op.f('blueprints__tenant_id_idx'), table_name='blueprints')
    op.drop_index(
        op.f('deployment_update_steps__tenant_id_idx'),
        table_name='deployment_update_steps')
    op.drop_index(op.f('deployments__tenant_id_idx'), table_name='deployments')
    op.drop_index(op.f('events__tenant_id_idx'), table_name='events')
    op.drop_index(
        op.f('deployment_modifications__tenant_id_idx'),
        table_name='deployment_modifications')
    op.drop_index(
        op.f('deployment_updates__tenant_id_idx'),
        table_name='deployment_updates')
    op.drop_index(op.f('logs__tenant_id_idx'), table_name='logs')
    op.drop_index(
        op.f('node_instances__tenant_id_idx'), table_name='node_instances')
    op.drop_index(op.f('snapshots__tenant_id_idx'), table_name='snapshots')
    op.drop_index(op.f('secrets__tenant_id_idx'), table_name='secrets')
    op.drop_index(op.f('plugins__tenant_id_idx'), table_name='plugins')
    op.drop_index(op.f('nodes__tenant_id_idx'), table_name='nodes')
    op.drop_index(op.f('executions__tenant_id_idx'), table_name='executions')

    # duplicated indexes in 4.4
    op.create_index('ix_blueprints_id', 'blueprints', ['id'], unique=False)
    op.create_index(
        'ix_blueprints_created_at', 'blueprints', ['created_at'], unique=False)

    op.create_index(
        'ix_deployment_modifications_id',
        'deployment_modifications', ['id'],
        unique=False)
    op.create_index(
        'ix_deployment_modifications_ended_at',
        'deployment_modifications', ['ended_at'],
        unique=False)
    op.create_index(
        'ix_deployment_modifications_created_at',
        'deployment_modifications', ['created_at'],
        unique=False)

    op.create_index(
        'ix_deployment_update_steps_id',
        'deployment_update_steps', ['id'],
        unique=False)
    op.create_index(
        'ix_deployment_updates_id', 'deployment_updates', ['id'], unique=False)
    op.create_index(
        'ix_deployment_updates_created_at',
        'deployment_updates', ['created_at'],
        unique=False)

    op.create_index('ix_events_id', 'events', ['id'], unique=False)
    op.create_index('ix_logs_id', 'logs', ['id'], unique=False)

    op.create_index('ix_deployments_id', 'deployments', ['id'], unique=False)
    op.create_index(
        'ix_deployments_created_at',
        'deployments', ['created_at'],
        unique=False)

    op.create_index(
        'ix_plugins_uploaded_at', 'plugins', ['uploaded_at'], unique=False)
    op.create_index(
        'ix_plugins_package_name', 'plugins', ['package_name'], unique=False)
    op.create_index('ix_plugins_id', 'plugins', ['id'], unique=False)
    op.create_index(
        'ix_plugins_archive_name', 'plugins', ['archive_name'], unique=False)

    op.create_index('ix_nodes_type', 'nodes', ['type'], unique=False)
    op.create_index('ix_nodes_id', 'nodes', ['id'], unique=False)
    op.create_index(
        'ix_node_instances_id', 'node_instances', ['id'], unique=False)

    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_index('ix_tenants_name', 'tenants', ['name'], unique=True)
    op.create_index('ix_roles_name', 'roles', ['name'], unique=True)

    op.create_index('ix_snapshots_id', 'snapshots', ['id'], unique=False)
    op.create_index(
        'ix_snapshots_created_at', 'snapshots', ['created_at'], unique=False)

    op.create_index('ix_secrets_id', 'secrets', ['id'], unique=False)
    op.create_index(
        'ix_secrets_created_at', 'secrets', ['created_at'], unique=False)

    op.create_index('ix_groups_name', 'groups', ['name'], unique=True)
    op.create_index('ix_groups_ldap_dn', 'groups', ['ldap_dn'], unique=True)

    op.create_index('ix_executions_id', 'executions', ['id'], unique=False)
    op.create_index(
        'ix_executions_created_at', 'executions', ['created_at'], unique=False)

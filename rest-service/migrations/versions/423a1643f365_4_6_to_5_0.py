
"""
4_6 to 5_0

- Add token field to executions
- Add config table
- Add sites table

Revision ID: 423a1643f365
Revises: 9516df019579
Create Date: 2019-02-21 13:00:46.042338

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from manager_rest.storage.models import User
from manager_rest.storage.models_base import JSONString, UTCDateTime

from cloudify.models_states import VisibilityState

# revision identifiers, used by Alembic.
revision = '423a1643f365'
down_revision = '9516df019579'
branch_labels = None
depends_on = None


LOG_LEVELS_ENUM = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


def upgrade():
    op.add_column('executions', sa.Column('token',
                                          sa.String(length=100),
                                          nullable=True))
    config_table = op.create_table(
        'config',
        sa.Column('name', sa.Text, primary_key=True),
        sa.Column('value', JSONString(), nullable=False),
        sa.Column('schema', JSONString(), nullable=True),
        sa.Column('is_editable', sa.Boolean, default=True),
        sa.Column('updated_at', UTCDateTime()),
        sa.Column('scope', sa.Text, primary_key=True),
        sa.Column(
            '_updater_id',
            sa.Integer,
            sa.ForeignKey(User.id, ondelete='SET NULL'),
            nullable=True,
            index=False,
            primary_key=False,
        )
    )
    op.bulk_insert(
        config_table,
        [
            dict(
                name='rest_service_log_path',
                value='/var/log/cloudify/rest/cloudify-rest-service.log',
                scope='rest',
                schema=None,
                is_editable=False
            ),
            dict(
                name='rest_service_log_level',
                value='INFO',
                scope='rest',
                schema={'type': 'string', 'enum': LOG_LEVELS_ENUM},
                is_editable=True
            ),
            dict(
                name='ldap_server',
                value=op.inline_literal('null'),
                scope='rest',
                schema={'type': 'string'},
                is_editable=True
            ),
            dict(
                name='ldap_username',
                value=op.inline_literal('null'),
                scope='rest',
                schema={'type': 'string'},
                is_editable=True
            ),
            dict(
                name='ldap_password',
                value=op.inline_literal('null'),
                scope='rest',
                schema={'type': 'string'},
                is_editable=True
            ),
            dict(
                name='ldap_domain',
                value=op.inline_literal('null'),
                scope='rest',
                schema={'type': 'string'},
                is_editable=True
            ),
            dict(
                name='ldap_is_active_directory',
                value=op.inline_literal('null'),
                scope='rest',
                schema={'type': 'boolean'},
                is_editable=True
            ),
            dict(
                name='ldap_dn_extra',
                value=op.inline_literal('null'),
                scope='rest',
                schema=None,
                is_editable=True
            ),
            dict(
                name='ldap_timeout',
                value=5.0,
                scope='rest',
                schema={'type': 'number'},
                is_editable=True
            ),
            dict(
                name='ldap_nested_levels',
                value=1,
                scope='rest',
                schema={'type': 'number', 'minimum': 1},
                is_editable=True
            ),
            dict(
                name='file_server_root',
                value='/opt/manager/resources',
                scope='rest',
                schema=None,
                is_editable=False
            ),
            dict(
                name='file_server_url',
                value='http://127.0.0.1:53333/resources',
                scope='rest',
                schema=None,
                is_editable=False
            ),
            dict(
                name='insecure_endpoints_disabled',
                value=True,
                scope='rest',
                schema={'type': 'boolean'},
                is_editable=False
            ),
            dict(
                name='maintenance_folder',
                value='/opt/manager/maintenance',
                scope='rest',
                schema=None,
                is_editable=False
            ),
            dict(
                name='min_available_memory_mb',
                value=100,
                scope='rest',
                schema={'type': 'number', 'minimum': 0},
                is_editable=True
            ),
            dict(
                name='failed_logins_before_account_lock',
                value=4,
                scope='rest',
                schema={'type': 'number', 'minimum': 1},
                is_editable=True
            ),
            dict(
                name='account_lock_period',
                value=-1,
                scope='rest',
                schema={'type': 'number', 'minimum': -1},
                is_editable=True
            ),
            dict(
                name='public_ip',
                value=op.inline_literal('null'),
                scope='rest',
                schema=None,
                is_editable=False
            ),
            dict(
                name='default_page_size',
                value=1000,
                scope='rest',
                schema={'type': 'number', 'minimum': 1},
                is_editable=True
            ),

            dict(
                name='max_workers',
                value=5,
                scope='mgmtworker',
                schema={'type': 'number', 'minimum': 1},
                is_editable=True
            ),
            dict(
                name='min_workers',
                value=2,
                scope='mgmtworker',
                schema={'type': 'number', 'minimum': 1},
                is_editable=True
            ),
            dict(
                name='broker_port',
                value=5671,
                scope='agent',
                schema={'type': 'number', 'minimum': 1, 'maximum': 65535},
                is_editable=True
            ),
            dict(
                name='min_workers',
                value=2,
                scope='agent',
                schema={'type': 'number', 'minimum': 1},
                is_editable=True
            ),
            dict(
                name='max_workers',
                value=5,
                scope='agent',
                schema={'type': 'number', 'minimum': 1},
                is_editable=True
            ),
            dict(
                name='heartbeat',
                value=30,
                scope='agent',
                schema={'type': 'number', 'minimum': 0},
                is_editable=True
            ),
            dict(
                name='log_level',
                value='info',
                scope='agent',
                schema={'type': 'string', 'enum': LOG_LEVELS_ENUM},
                is_editable=True
            ),
            dict(
                name='task_retries',
                value=60,
                scope='workflow',
                schema={'type': 'number', 'minimum': -1},
                is_editable=True
            ),
            dict(
                name='task_retry_interval',
                value=15,
                scope='workflow',
                schema={'type': 'number', 'minimum': 0},
                is_editable=True
            ),
            dict(
                name='subgraph_retries',
                value=0,
                scope='workflow',
                schema={'type': 'number', 'minimum': -1},
                is_editable=True
            )
        ]
    )

    op.create_table(
        'certificates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.Text(), unique=True, nullable=False),
        sa.Column('value', sa.Text(), unique=False, nullable=False),
        sa.Column('updated_at', UTCDateTime(), nullable=True),
        sa.Column('_updater_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['_updater_id'],
            [u'users.id'],
            ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('certificates_pkey'))
    )
    op.create_table(
        'managers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('hostname', sa.Text(), unique=True, nullable=False),
        sa.Column('private_ip', sa.Text(), unique=True, nullable=False),
        sa.Column('public_ip', sa.Text(), unique=True, nullable=False),
        sa.Column('version', sa.Text(), nullable=False),
        sa.Column('edition', sa.Text(), nullable=False),
        sa.Column('distribution', sa.Text(), nullable=False),
        sa.Column('distro_release', sa.Text(), nullable=False),
        sa.Column('fs_sync_node_id', sa.Text(), nullable=True),
        sa.Column('networks', JSONString(), nullable=True),
        sa.Column('_ca_cert_id', sa.Integer(), nullable=False),

        sa.ForeignKeyConstraint(
            ['_ca_cert_id'],
            [u'certificates.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('managers_pkey'))
    )
    op.create_table(
        'rabbitmq_brokers',
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('host', sa.Text(), nullable=False),
        sa.Column('management_host', sa.Text(), nullable=True),
        sa.Column('port', sa.Integer()),
        sa.Column('username', sa.Text(), nullable=True),
        sa.Column('password', sa.Text(), nullable=True),
        sa.Column('params', JSONString(), nullable=True),
        sa.Column('networks', JSONString(), nullable=True),
        sa.Column('_ca_cert_id', sa.Integer(), nullable=False),

        sa.ForeignKeyConstraint(
            ['_ca_cert_id'],
            [u'certificates.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('name', name=op.f('rabbitmq_brokers_pkey'))
    )

    op.add_column('deployment_updates', sa.Column(
        'central_plugins_to_install',
        sa.PickleType()))
    op.add_column('deployment_updates', sa.Column(
        'central_plugins_to_uninstall',
        sa.PickleType()))

    op.add_column('blueprints',
                  sa.Column('is_hidden',
                            sa.Boolean(),
                            nullable=False,
                            server_default='f'))

    _create_sites_table()
    _create_plugins_update_table()


def downgrade():
    op.drop_column('executions', 'token')
    op.drop_table('config')
    op.drop_table('managers')
    op.drop_table('rabbitmq_brokers')
    op.drop_table('certificates')

    op.drop_column('deployment_updates', 'central_plugins_to_install')
    op.drop_column('deployment_updates', 'central_plugins_to_uninstall')

    op.drop_column('blueprints', 'is_hidden')

    _drop_sites_table()
    _drop_plugins_update_table()


def _create_plugins_update_table():
    visibility_enum = postgresql.ENUM(*VisibilityState.STATES,
                                      name='visibility_states',
                                      create_type=False)

    op.create_table(
        'plugins_updates',
        sa.Column('_storage_id',
                  sa.Integer(),
                  autoincrement=True,
                  nullable=False),
        sa.Column('id', sa.Text(), nullable=True),
        sa.Column('visibility',
                  visibility_enum,
                  nullable=True),
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('state', sa.Text(), nullable=True),
        sa.Column('deployments_to_update',
                  sa.PickleType(),
                  nullable=True),
        sa.Column('forced', sa.Boolean(), default=False),
        sa.Column('_original_blueprint_fk',
                  sa.Integer(),
                  nullable=False),
        sa.Column('_temp_blueprint_fk',
                  sa.Integer(),
                  nullable=True),
        sa.Column('_execution_fk', sa.Integer(), nullable=True),
        sa.Column('_tenant_id', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['_creator_id'],
                                [u'users.id'],
                                name=op.f('plugins_updates__creator_id_fkey'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_execution_fk'],
            [u'executions._storage_id'],
            name=op.f('plugins_updates__execution_fk_fkey'),
            ondelete='SET NULL'),
        sa.ForeignKeyConstraint(
            ['_original_blueprint_fk'],
            [u'blueprints._storage_id'],
            name=op.f('plugins_updates__original_blueprint_fk_fkey'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_temp_blueprint_fk'],
            [u'blueprints._storage_id'],
            name=op.f('plugins_updates__temp_blueprint_fk_fkey'),
            ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['_tenant_id'],
                                [u'tenants.id'],
                                name=op.f('plugins_updates__tenant_id_fkey'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('_storage_id',
                                name=op.f('plugins_updates_pkey'))
    )
    op.create_index(op.f('plugins_updates__tenant_id_idx'),
                    'plugins_updates',
                    ['_tenant_id'],
                    unique=False)
    op.create_index(op.f('plugins_updates_created_at_idx'),
                    'plugins_updates',
                    ['created_at'],
                    unique=False)
    op.create_index(op.f('plugins_updates_id_idx'),
                    'plugins_updates',
                    ['id'],
                    unique=False)


def _drop_plugins_update_table():
    op.drop_index(op.f('plugins_updates_id_idx'), table_name='plugins_updates')
    op.drop_index(op.f('plugins_updates_created_at_idx'),
                  table_name='plugins_updates')
    op.drop_index(op.f('plugins_updates__tenant_id_idx'),
                  table_name='plugins_updates')
    op.drop_table('plugins_updates')


def _create_sites_table():
    visibility_enum = postgresql.ENUM(*VisibilityState.STATES,
                                      name='visibility_states',
                                      create_type=False)

    op.create_table(
        'sites',
        sa.Column('_storage_id', sa.Integer(), autoincrement=True,
                  nullable=False),
        sa.Column('id', sa.Text(), nullable=True),
        sa.Column('visibility', visibility_enum, nullable=True),
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('_tenant_id', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),

        sa.ForeignKeyConstraint(['_creator_id'],
                                ['users.id'],
                                name=op.f('sites__creator_id_fkey'),
                                ondelete='CASCADE'),

        sa.ForeignKeyConstraint(['_tenant_id'],
                                ['tenants.id'],
                                name=op.f('sites__tenant_id_fkey'),
                                ondelete='CASCADE'),

        sa.PrimaryKeyConstraint('_storage_id', name=op.f('sites_pkey'))
    )

    op.create_index(op.f('sites__tenant_id_idx'),
                    'sites',
                    ['_tenant_id'],
                    unique=False)
    op.create_index(op.f('sites_created_at_idx'),
                    'sites',
                    ['created_at'],
                    unique=False)
    op.create_index(op.f('sites_id_idx'),
                    'sites',
                    ['id'],
                    unique=False)

    # Add sites FK to deployments table
    op.add_column('deployments', sa.Column('_site_fk',
                                           sa.Integer(),
                                           nullable=True))
    op.create_foreign_key(op.f('deployments__site_fk_fkey'),
                          'deployments',
                          'sites',
                          ['_site_fk'],
                          ['_storage_id'],
                          ondelete='SET NULL')


def _drop_sites_table():
    op.drop_constraint(op.f('deployments__site_fk_fkey'),
                       'deployments',
                       type_='foreignkey')
    op.drop_column('deployments', '_site_fk')
    op.drop_index(op.f('sites_id_idx'), table_name='sites')
    op.drop_index(op.f('sites_created_at_idx'), table_name='sites')
    op.drop_index(op.f('sites__tenant_id_idx'), table_name='sites')
    op.drop_table('sites')

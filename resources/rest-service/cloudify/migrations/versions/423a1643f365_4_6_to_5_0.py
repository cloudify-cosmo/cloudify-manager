
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
from sqlalchemy import orm
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.declarative import declarative_base

from manager_rest.storage.models import User
from manager_rest.storage.models_base import JSONString, UTCDateTime

from cloudify.models_states import VisibilityState

# revision identifiers, used by Alembic.
revision = '423a1643f365'
down_revision = '9516df019579'
branch_labels = None
depends_on = None


Base = declarative_base()

LOG_LEVELS_ENUM = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


class Config(Base):
    __tablename__ = 'config'

    name = sa.Column(sa.Text, primary_key=True)
    value = sa.Column(JSONString(), nullable=False)
    schema = sa.Column(JSONString(), nullable=True)
    is_editable = sa.Column(sa.Boolean, default=True)
    updated_at = sa.Column(UTCDateTime())
    scope = sa.Column(sa.Text, primary_key=True)
    _updater_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(User.id, ondelete='SET NULL'),
        nullable=True,
        index=False,
        primary_key=False,
    )


def upgrade():
    op.add_column('executions', sa.Column('token',
                                          sa.String(length=100),
                                          nullable=True))

    bind = op.get_bind()
    session = orm.Session(bind=bind)
    Config.__table__.create(bind)

    session.add_all([
        Config(
            name='rest_service_log_path',
            value='/var/log/cloudify/rest/cloudify-rest-service.log',
            scope='rest',
            schema=None,
            is_editable=False
        ),
        Config(
            name='rest_service_log_level',
            value='INFO',
            scope='rest',
            schema={'type': 'string', 'enum': LOG_LEVELS_ENUM},
            is_editable=True
        ),
        Config(
            name='ldap_server',
            value=None,
            scope='rest',
            schema={'type': 'string'},
            is_editable=True
        ),
        Config(
            name='ldap_username',
            value=None,
            scope='rest',
            schema={'type': 'string'},
            is_editable=True
        ),
        Config(
            name='ldap_password',
            value=None,
            scope='rest',
            schema={'type': 'string'},
            is_editable=True
        ),
        Config(
            name='ldap_domain',
            value=None,
            scope='rest',
            schema={'type': 'string'},
            is_editable=True
        ),
        Config(
            name='ldap_is_active_directory',
            value=None,
            scope='rest',
            schema={'type': 'boolean'},
            is_editable=True
        ),
        Config(
            name='ldap_dn_extra',
            value=None,
            scope='rest',
            schema=None,
            is_editable=True
        ),
        Config(
            name='ldap_timeout',
            value=5.0,
            scope='rest',
            schema={'type': 'number'},
            is_editable=True
        ),
        Config(
            name='ldap_nested_levels',
            value=1,
            scope='rest',
            schema={'type': 'number', 'minimum': 1},
            is_editable=True
        ),
        Config(
            name='file_server_root',
            value='/opt/manager/resources',
            scope='rest',
            schema=None,
            is_editable=False
        ),
        Config(
            name='file_server_url',
            value='http://127.0.0.1:53333/resources',
            scope='rest',
            schema=None,
            is_editable=False
        ),
        Config(
            name='insecure_endpoints_disabled',
            value=True,
            scope='rest',
            schema={'type': 'boolean'},
            is_editable=False
        ),
        Config(
            name='maintenance_folder',
            value='/opt/manager/maintenance',
            scope='rest',
            schema=None,
            is_editable=False
        ),
        Config(
            name='min_available_memory_mb',
            value=100,
            scope='rest',
            schema={'type': 'number', 'minimum': 0},
            is_editable=True
        ),
        Config(
            name='failed_logins_before_account_lock',
            value=4,
            scope='rest',
            schema={'type': 'number', 'minimum': 1},
            is_editable=True
        ),
        Config(
            name='account_lock_period',
            value=-1,
            scope='rest',
            schema={'type': 'number', 'minimum': -1},
            is_editable=True
        ),
        Config(
            name='public_ip',
            value=None,
            scope='rest',
            schema=None,
            is_editable=False
        ),
        Config(
            name='default_page_size',
            value=1000,
            scope='rest',
            schema={'type': 'number', 'minimum': 1},
            is_editable=True
        ),

        Config(
            name='max_workers',
            value=5,
            scope='mgmtworker',
            schema={'type': 'number', 'minimum': 1},
            is_editable=True
        ),
        Config(
            name='min_workers',
            value=2,
            scope='mgmtworker',
            schema={'type': 'number', 'minimum': 1},
            is_editable=True
        ),
        Config(
            name='broker_port',
            value=5671,
            scope='agent',
            schema={'type': 'number', 'minimum': 1, 'maximum': 65535},
            is_editable=True
        ),
        Config(
            name='min_workers',
            value=2,
            scope='agent',
            schema={'type': 'number', 'minimum': 1},
            is_editable=True
        ),
        Config(
            name='max_workers',
            value=5,
            scope='agent',
            schema={'type': 'number', 'minimum': 1},
            is_editable=True
        ),
        Config(
            name='heartbeat',
            value=30,
            scope='agent',
            schema={'type': 'number', 'minimum': 0},
            is_editable=True
        ),
        Config(
            name='log_level',
            value='info',
            scope='agent',
            schema={'type': 'string', 'enum': LOG_LEVELS_ENUM}
        )
    ])
    session.commit()

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

    _create_sites_table()


def downgrade():
    op.drop_column('executions', 'token')
    op.drop_table('config')
    op.drop_table('managers')
    op.drop_table('rabbitmq_brokers')
    op.drop_table('certificates')
    _drop_sites_table()


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

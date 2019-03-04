
"""
4_6 to 5_0

- Add token field to executions
- Add config table

Revision ID: 423a1643f365
Revises: 9516df019579
Create Date: 2019-02-21 13:00:46.042338

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.dialects import postgresql
from manager_rest.storage.models import User
from manager_rest.storage.models_base import JSONString, UTCDateTime
from sqlalchemy.ext.declarative import declarative_base


# revision identifiers, used by Alembic.
revision = '423a1643f365'
down_revision = '9516df019579'
branch_labels = None
depends_on = None


Base = declarative_base()


class Config(Base):
    __tablename__ = 'config'

    name = sa.Column(sa.Text, primary_key=True)
    value = sa.Column(JSONString(), nullable=False)
    schema = sa.Column(JSONString(), nullable=True)
    is_editable = sa.Column(sa.Boolean, default=True)
    updated_at = sa.Column(UTCDateTime())
    scope = sa.Column(postgresql.ARRAY(sa.Text))
    _updater_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(User.id, ondelete='CASCADE'),
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
            scope=['rest'],
            schema=None,
            is_editable=False
        ),
        Config(
            name='rest_service_log_level',
            value='INFO',
            scope=['rest'],
            schema={'type': 'string', 'enum': ['DEBUG', 'INFO', 'WARNING',
                                               'ERROR', 'CRITICAL']},
            is_editable=True
        ),
        Config(
            name='ldap_server',
            value=None,
            scope=['rest'],
            schema={'type': 'string'},
            is_editable=True
        ),
        Config(
            name='ldap_username',
            value=None,
            scope=['rest'],
            schema={'type': 'string'},
            is_editable=True
        ),
        Config(
            name='ldap_password',
            value=None,
            scope=['rest'],
            schema={'type': 'string'},
            is_editable=True
        ),
        Config(
            name='ldap_domain',
            value=None,
            scope=['rest'],
            schema={'type': 'string'},
            is_editable=True
        ),
        Config(
            name='ldap_is_active_directory',
            value=None,
            scope=['rest'],
            schema={'type': 'boolean'},
            is_editable=True
        ),
        Config(
            name='ldap_dn_extra',
            value=None,
            scope=['rest'],
            schema=None,
            is_editable=True
        ),
        Config(
            name='ldap_timeout',
            value=5.0,
            scope=['rest'],
            schema={'type': 'number'},
            is_editable=True
        ),
        Config(
            name='file_server_root',
            value='/opt/manager/resources',
            scope=['rest'],
            schema=None,
            is_editable=False
        ),
        Config(
            name='file_server_url',
            value='http://127.0.0.1:53333/resources',
            scope=['rest'],
            schema=None,
            is_editable=False
        ),
        Config(
            name='insecure_endpoints_disabled',
            value=True,
            scope=['rest'],
            schema={'type': 'boolean'},
            is_editable=False
        ),
        Config(
            name='maintenance_folder',
            value='/opt/manager/maintenance',
            scope=['rest'],
            schema=None,
            is_editable=False
        ),
        Config(
            name='min_available_memory_mb',
            value=100,
            scope=['rest'],
            schema={'type': 'number', 'minimum': 0},
            is_editable=True
        ),
        Config(
            name='failed_logins_before_account_lock',
            value=4,
            scope=['rest'],
            schema={'type': 'number', 'minimum': 1},
            is_editable=True
        ),
        Config(
            name='account_lock_period',
            value=-1,
            scope=['rest'],
            schema={'type': 'number', 'minimum': -1},
            is_editable=True
        ),
        Config(
            name='public_ip',
            value=None,
            scope=['rest'],
            schema=None,
            is_editable=False
        ),
        Config(
            name='default_page_size',
            value=1000,
            scope=['rest'],
            schema={'type': 'number', 'minimum': 1},
            is_editable=True
        ),

        Config(
            name='mgmtworker_max_workers',
            value=5,
            scope=['mgmtworker'],
            schema={'type': 'number', 'minimum': 1},
            is_editable=True
        ),
        Config(
            name='mgmtworker_min_workers',
            value=2,
            scope=['mgmtworker'],
            schema={'type': 'number', 'minimum': 1},
            is_editable=True
        )
    ])
    session.commit()


def downgrade():
    op.drop_column('executions', 'token')
    op.drop_table('config')

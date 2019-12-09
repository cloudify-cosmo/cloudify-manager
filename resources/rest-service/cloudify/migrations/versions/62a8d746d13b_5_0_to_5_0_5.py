"""
5_0 to 5_0_5


Revision ID: 62a8d746d13b
Revises: 423a1643f365
Create Date: 2019-08-23 13:36:03.985636

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.ext.declarative import declarative_base

from manager_rest.storage.models import User
from manager_rest.storage.models_base import JSONString, UTCDateTime

# revision identifiers, used by Alembic.
revision = '62a8d746d13b'
down_revision = '423a1643f365'
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
    scope = sa.Column(sa.Text, primary_key=True)
    _updater_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(User.id, ondelete='SET NULL'),
        nullable=True,
        index=False,
        primary_key=False,
    )


def upgrade():
    op.add_column(
        'executions',
        sa.Column('blueprint_id', sa.Text(), nullable=True))
    op.add_column(
        'deployments',
        sa.Column('runtime_only_evaluation', sa.Boolean(), nullable=True))
    op.add_column(
        'deployment_updates',
        sa.Column('runtime_only_evaluation', sa.Boolean(), nullable=True))
    op.add_column(
        'node_instances',
        sa.Column('index', sa.Integer(), nullable=True))

    bind = op.get_bind()
    session = orm.Session(bind=bind)
    session.add(
        Config(
            name='ldap_ca_path',
            value=None,
            scope='rest',
            schema={'type': 'string'},
            is_editable=True
        )
    )
    session.commit()

    _create_db_nodes_table()

    op.add_column('managers', sa.Column('node_id', sa.Text(), nullable=False))
    op.create_unique_constraint(op.f('managers_node_id_key'), 'managers',
                                ['node_id'])
    op.add_column('rabbitmq_brokers',
                  sa.Column('is_external',
                            sa.Boolean(),
                            nullable=False,
                            server_default='f'))
    op.add_column('rabbitmq_brokers',
                  sa.Column('node_id', sa.Text(), nullable=False))
    op.create_unique_constraint(op.f('rabbitmq_brokers_node_id_key'),
                                'rabbitmq_brokers', ['node_id'])
    op.create_index(
        op.f('node_instances__node_fk_idx'),
        'node_instances',
        ['_node_fk'],
        unique=False)
    op.create_index(
        op.f('nodes__deployment_fk_idx'),
        'nodes',
        ['_deployment_fk'],
        unique=False)


def downgrade():
    op.drop_index(
        op.f('nodes__deployment_fk_idx'),
        table_name='nodes')
    op.drop_index(
        op.f('node_instances__node_fk_idx'),
        table_name='node_instances')

    op.drop_column('deployment_updates', 'runtime_only_evaluation')
    op.drop_column('deployments', 'runtime_only_evaluation')
    op.drop_column('executions', 'blueprint_id')
    op.drop_column('node_instances', 'index')

    bind = op.get_bind()
    session = orm.Session(bind=bind)

    ldap_ca_path = session.query(Config).filter_by(
        name='ldap_ca_path',
        scope='rest',
    ).one()
    session.delete(ldap_ca_path)
    session.commit()

    op.drop_constraint(
        op.f('rabbitmq_brokers_node_id_key'),
        'rabbitmq_brokers',
        type_='unique'
    )
    op.drop_column('rabbitmq_brokers', 'node_id')
    op.drop_column('rabbitmq_brokers', 'is_external')
    op.drop_constraint(
        op.f('managers_node_id_key'),
        'managers',
        type_='unique'
    )
    op.drop_column('managers', 'node_id')
    op.drop_table('db_nodes')


def _create_db_nodes_table():
    op.create_table(
        'db_nodes',
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('node_id', sa.Text(), nullable=False),
        sa.Column('host', sa.Text(), nullable=False),
        sa.Column('is_external', sa.Boolean(), nullable=False,
                  server_default='f'),
        sa.PrimaryKeyConstraint('name', name=op.f('db_nodes_pkey')),
        sa.UniqueConstraint('node_id', name=op.f('db_nodes_node_id_key')),
        sa.UniqueConstraint('host', name=op.f('db_nodes_host_key'))
    )

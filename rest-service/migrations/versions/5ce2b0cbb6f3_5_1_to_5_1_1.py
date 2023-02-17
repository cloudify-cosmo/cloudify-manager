"""5_1 to 5_1_1

- Add column topology_order to deployment_update_steps table

Revision ID: 5ce2b0cbb6f3
Revises: 387fcd049efb
Create Date: 2020-11-09 15:12:12.055532

"""
import yaml
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column, select

from manager_rest.storage.models_base import UTCDateTime

# revision identifiers, used by Alembic.
revision = '5ce2b0cbb6f3'
down_revision = '387fcd049efb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'deployment_update_steps',
        sa.Column('topology_order',
                  sa.Integer(),
                  nullable=False,
                  server_default="0"))
    create_deployments_labels_table()
    permissions_table = _create_permissions_table()
    _load_permissions(permissions_table)
    _create_maintenance_mode_table()
    op.add_column(
        'roles',
        sa.Column('type',
                  sa.Text(),
                  nullable=False,
                  server_default='tenant_role'))


def downgrade():
    op.drop_column('deployment_update_steps', 'topology_order')
    drop_deployments_labels_table()
    op.drop_table('permissions')
    op.drop_column('roles', 'type')
    op.drop_index(op.f('maintenance_mode__requested_by_idx'),
                  table_name='maintenance_mode')
    op.drop_table('maintenance_mode')


def create_deployments_labels_table():
    _create_labels_table('deployments_labels',
                         '_deployment_fk',
                         u'deployments._storage_id',
                         '_deployment_idx')


def drop_deployments_labels_table():
    op.drop_table('deployments_labels')


def _create_labels_table(table_name, fk_column, fk_refcolumn, fk_index):
    """
    This is an auxiliary function to create an object's labels table.

    :param table_name: The table name. E.g. deployments_labels
    :param fk_column: The object's foreign key column name. E.g. _deployment_fk
    :param fk_refcolumn: The object's foreign key reference column. E.g.
                         u'deployments._storage_id'
    :param fk_index: The object's foreign key index name. E.g. _deployment_idx
    """
    op.create_table(
        table_name,
        sa.Column('id',
                  sa.Integer(),
                  autoincrement=True,
                  nullable=False),
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column(fk_column, sa.Integer(), nullable=False),
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            [fk_column],
            [fk_refcolumn],
            name=op.f('{0}_{1}'.format(table_name, fk_column)),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_creator_id'],
            [u'users.id'],
            name=op.f('{0}__creator_id_fkey'.format(table_name)),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint(
            'id',
            name=op.f('{0}_pkey'.format(table_name))),
        sa.UniqueConstraint(
            'key', 'value', fk_column, name=op.f('{0}_key_value_key'))
    )
    op.create_index(op.f('{0}_created_at_idx'.format(table_name)),
                    table_name,
                    ['created_at'],
                    unique=False)
    op.create_index(op.f('{0}__creator_id_idx'.format(table_name)),
                    table_name,
                    ['_creator_id'],
                    unique=False)
    op.create_index(op.f('{0}_key_idx'.format(table_name)),
                    table_name,
                    ['key'],
                    unique=False)
    op.create_index(op.f('{0}_{1}'.format(table_name, fk_index)),
                    table_name,
                    [fk_column],
                    unique=False)


def _create_permissions_table():
    return op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['role_id'],
            [u'roles.id'],
            ondelete='CASCADE',
        ),
    )


def _create_maintenance_mode_table():
    op.create_table(
        'maintenance_mode',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('activation_requested_at', UTCDateTime(), nullable=False),
        sa.Column('activated_at', UTCDateTime(), nullable=True),
        sa.Column('_requested_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['_requested_by'],
            ['users.id'],
            name=op.f('maintenance_mode__requested_by_fkey'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('maintenance_mode_pkey'))
    )
    op.create_index(
        op.f('maintenance_mode__requested_by_idx'),
        'maintenance_mode',
        ['_requested_by'],
        unique=False)


def _load_permissions(permissions_table):
    """Load permissions from the conf file, if it exists."""
    try:
        with open('/opt/manager/authorization.conf') as f:
            data = yaml.safe_load(f)
            permissions = data['permissions']
    except (IOError, KeyError):
        return
    roles_table = table('roles', column('id'), column('name'))

    for permission, roles in permissions.items():
        for role in roles:
            op.execute(
                permissions_table.insert()
                .from_select(
                    ['name', 'role_id'],
                    select([
                        op.inline_literal(permission).label('name'),
                        roles_table.c.id
                    ])
                    .where(roles_table.c.name == op.inline_literal(role))
                    .limit(op.inline_literal(1))
                )
            )

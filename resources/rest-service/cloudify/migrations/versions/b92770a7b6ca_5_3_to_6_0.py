"""5_3 to 6_0

Revision ID: b92770a7b6ca
Revises: 396303c07e35
Create Date: 2021-04-12 09:33:44.399254

"""
from alembic import op
import sqlalchemy as sa

from manager_rest.storage import models

# revision identifiers, used by Alembic.
revision = 'b92770a7b6ca'
down_revision = '396303c07e35'
branch_labels = None
depends_on = None


def upgrade():
    _add_execution_group_fk()
    _add_new_execution_columns()
    _drop_events_id()
    _drop_logs_id()
    _add_deployments_display_name_column()
    _add_depgroups_creation_counter()


def downgrade():
    _drop_depgroups_creation_counter()
    _drop_deployments_display_name_column()
    _create_logs_id()
    _create_events_id()
    _drop_execution_group_fk()
    _drop_new_execution_columns()


def _drop_events_id():
    op.drop_index('events_id_idx', table_name='events')
    op.drop_column('events', 'id')


def _drop_logs_id():
    op.drop_index('logs_id_idx', table_name='logs')
    op.drop_column('logs', 'id')


def _create_logs_id():
    op.add_column('logs', sa.Column('id', sa.Text(),
                  autoincrement=False, nullable=True))
    op.create_index('logs_id_idx', 'logs', ['id'],
                    unique=False)


def _create_events_id():
    op.add_column('events', sa.Column('id', sa.Text(),
                  autoincrement=False, nullable=True))
    op.create_index('events_id_idx', 'events', ['id'],
                    unique=False)


def _add_new_execution_columns():
    op.add_column(
        'executions',
        sa.Column('allow_custom_parameters', sa.Boolean(),
                  server_default='false', nullable=False)
    )


def _drop_new_execution_columns():
    op.drop_column('executions', 'allow_custom_parameters')


def _add_execution_group_fk():
    op.add_column(
        'events',
        sa.Column('_execution_group_fk', sa.Integer(), nullable=True)
    )
    op.alter_column(
        'events',
        '_execution_fk',
        existing_type=sa.Integer(),
        nullable=True
    )
    op.create_index(
        op.f('events__execution_group_fk_idx'),
        'events',
        ['_execution_group_fk'],
        unique=False
    )
    op.create_foreign_key(
        op.f('events__execution_group_fk_fkey'),
        'events',
        'execution_groups',
        ['_execution_group_fk'],
        ['_storage_id'],
        ondelete='CASCADE',
    )
    op.create_check_constraint(
        'events__one_fk_not_null',
        'events',
        '(_execution_fk IS NOT NULL) != (_execution_group_fk IS NOT NULL)'
    )

    op.add_column(
        'logs',
        sa.Column('_execution_group_fk', sa.Integer(), nullable=True)
    )
    op.alter_column(
        'logs',
        '_execution_fk',
        existing_type=sa.Integer(),
        nullable=True
    )
    op.create_index(
        op.f('logs__execution_group_fk_idx'),
        'logs',
        ['_execution_group_fk'],
        unique=False
    )
    op.create_foreign_key(
        op.f('logs__execution_group_fk_fkey'),
        'logs',
        'execution_groups',
        ['_execution_group_fk'],
        ['_storage_id'],
        ondelete='CASCADE'
    )
    op.create_check_constraint(
        'logs__one_fk_not_null',
        'logs',
        '(_execution_fk IS NOT NULL) != (_execution_group_fk IS NOT NULL)'
    )


def _drop_execution_group_fk():
    op.drop_constraint(
        op.f('logs__one_fk_not_null'),
        'logs',
        type_='check',
    )
    op.drop_constraint(
        op.f('logs__execution_group_fk_fkey'),
        'logs',
        type_='foreignkey'
    )
    op.drop_index(
        op.f('logs__execution_group_fk_idx'),
        table_name='logs'
    )
    op.execute(
        models.Log.__table__
        .delete()
        .where(models.Log.__table__.c._execution_fk.is_(None))
    )
    op.alter_column(
        'logs',
        '_execution_fk',
        existing_type=sa.Integer(),
        nullable=False
    )
    op.drop_column(
        'logs',
        '_execution_group_fk'
    )

    op.drop_constraint(
        op.f('events__one_fk_not_null'),
        'events',
        type_='check',
    )
    op.drop_constraint(
        op.f('events__execution_group_fk_fkey'),
        'events',
        type_='foreignkey'
    )
    op.drop_index(
        op.f('events__execution_group_fk_idx'),
        table_name='events'
    )
    op.execute(
        models.Event.__table__
        .delete()
        .where(models.Event.__table__.c._execution_fk.is_(None))
    )
    op.alter_column(
        'events',
        '_execution_fk',
        existing_type=sa.Integer(),
        nullable=False
    )
    op.drop_column(
        'events',
        '_execution_group_fk'
    )


def _add_deployments_display_name_column():
    op.add_column('deployments',
                  sa.Column('display_name', sa.Text(), nullable=True))
    op.execute(models.Deployment.__table__.update().values(
        display_name=models.Deployment.__table__.c.id))

    op.alter_column(
        'deployments',
        'display_name',
        existing_type=sa.Text(),
        nullable=False
    )
    op.create_index(op.f('deployments_display_name_idx'),
                    'deployments', ['display_name'], unique=False)


def _drop_deployments_display_name_column():
    op.drop_index(op.f('deployments_display_name_idx'),
                  table_name='deployments')
    op.drop_column('deployments', 'display_name')


def _add_depgroups_creation_counter():
    op.add_column(
        'deployment_groups',
        sa.Column('creation_counter', sa.Integer(), nullable=False,
                  server_default='0')
    )


def _drop_depgroups_creation_counter():
    op.drop_column('deployment_groups', 'creation_counter')

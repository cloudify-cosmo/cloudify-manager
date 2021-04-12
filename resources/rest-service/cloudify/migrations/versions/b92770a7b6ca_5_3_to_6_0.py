"""5_3 to 6_0

Revision ID: b92770a7b6ca
Revises: 396303c07e35
Create Date: 2021-04-12 09:33:44.399254

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b92770a7b6ca'
down_revision = '396303c07e35'
branch_labels = None
depends_on = None


def upgrade():
    _add_execution_group_fk()


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


def downgrade():
    _drop_execution_group_fk()


def _drop_execution_group_fk():
    op.drop_constraint(
        op.f('logs__one_fk_not_null'),
        'logs',
        type='check',
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
        type='check',
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

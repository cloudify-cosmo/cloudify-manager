"""Cloudify 6.1 to 6.2 DB migration

Revision ID: 03ad040e6f78
Revises: a31cb9e704d3
Create Date: 2021-08-19 11:21:00.361811

"""
import sqlalchemy as sa
from alembic import op
from manager_rest.storage.models_base import JSONString, UTCDateTime

# revision identifiers, used by Alembic.
revision = '03ad040e6f78'
down_revision = 'a31cb9e704d3'
branch_labels = None
depends_on = None

audit_operation = sa.Enum(
    'create', 'update', 'delete',
    name='audit_operation',
)

config_table = sa.table(
    'config',
    sa.Column('name', sa.Text),
    sa.Column('value', JSONString()),
    sa.Column('schema', JSONString()),
    sa.Column('is_editable', sa.Boolean),
    sa.Column('updated_at', UTCDateTime()),
    sa.Column('scope', sa.Text),
)


def upgrade():
    _create_audit_log_table()
    _add_config_manager_service_log()


def downgrade():
    _drop_config_manager_service_log()
    _drop_audit_log_table()


def _create_audit_log_table():
    op.create_table(
        'audit_log',
        sa.Column(
            '_storage_id', sa.Integer(),
            autoincrement=True, nullable=False),
        sa.Column(
            'ref_table', sa.Text(),
            nullable=False),
        sa.Column(
            'ref_id', sa.Integer(),
            nullable=False),
        sa.Column(
            'operation',
            audit_operation,
            nullable=False),
        sa.Column(
            'creator_name', sa.Text(),
            nullable=True),
        sa.Column(
            'execution_id', sa.Text(),
            nullable=True),
        sa.Column(
            'created_at', UTCDateTime(),
            nullable=False),
        sa.CheckConstraint(
            'creator_name IS NOT NULL OR execution_id IS NOT NULL',
            name='audit_log_creator_or_user_not_null'),
        sa.PrimaryKeyConstraint(
            '_storage_id',
            name=op.f('audit_log_pkey'))
    )
    op.create_index(
        op.f('audit_log_created_at_idx'),
        'audit_log', ['created_at'],
        unique=False)
    op.create_index(
        'audit_log_ref_idx',
        'audit_log', ['ref_table', 'ref_id'],
        unique=False)
    op.create_index(
        op.f('audit_log_ref_table_idx'),
        'audit_log', ['ref_table'],
        unique=False)


def _drop_audit_log_table():
    op.drop_index(op.f('audit_log_ref_table_idx'), table_name='audit_log')
    op.drop_index('audit_log_ref_idx', table_name='audit_log')
    op.drop_index(op.f('audit_log_created_at_idx'), table_name='audit_log')
    op.drop_table('audit_log')
    audit_operation.drop(op.get_bind())


def _add_config_manager_service_log():
    log_level_enums = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    op.bulk_insert(
        config_table,
        [
            dict(
                name='api_service_log_path',
                value='/var/log/cloudify/rest/cloudify-api-service.log',
                scope='rest',
                schema=None,
                is_editable=False
            ),
            dict(
                name='api_service_log_level',
                value='INFO',
                scope='rest',
                schema={'type': 'string', 'enum': log_level_enums},
                is_editable=True
            ),
        ]
    )


def _drop_config_manager_service_log():
    op.execute(
        config_table
        .delete()
        .where(
            (config_table.c.name == op.inline_literal(
                'api_service_log_path')) &  # NOQA
            (config_table.c.scope == op.inline_literal('rest'))
        )
    )
    op.execute(
        config_table
        .delete()
        .where(
            (config_table.c.name == op.inline_literal(
                'api_service_log_level')) &  # NOQA
            (config_table.c.scope == op.inline_literal('rest'))
        )
    )

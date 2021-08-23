"""Cloudify 6.1 to 6.2 DB migration

Revision ID: 03ad040e6f78
Revises: a31cb9e704d3
Create Date: 2021-08-19 11:21:00.361811

"""
from alembic import op
import sqlalchemy as sa

from manager_rest.storage.models_base import UTCDateTime

# revision identifiers, used by Alembic.
revision = '03ad040e6f78'
down_revision = 'a31cb9e704d3'
branch_labels = None
depends_on = None


def upgrade():
    _create_audit_log_table()


def downgrade():
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
            sa.Enum('create', 'update', 'delete', name='audit_operation'),
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
            '(creator_name IS NULL) != (execution_id IS NULL)',
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

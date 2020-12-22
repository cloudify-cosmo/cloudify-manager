"""5_1_1 to 5_1_2
- Update The configuration table for service management value
Revision ID: 9d261e90b1f3
Revises: 5ce2b0cbb6f3
Create Date: 2020-11-26 14:07:36.053518
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

from manager_rest.storage.models_base import JSONString, UTCDateTime

# revision identifiers, used by Alembic.
revision = '9d261e90b1f3'
down_revision = '5ce2b0cbb6f3'
branch_labels = None
depends_on = None

config_table = table(
    'config',
    column('name', sa.Text),
    column('value', JSONString()),
    column('schema', JSONString()),
    column('is_editable', sa.Boolean),
    column('updated_at', UTCDateTime()),
    column('scope', sa.Text),
)


def upgrade():
    _change_service_management_value('supervisord')


def downgrade():
    _change_service_management_value('systemd')


def _change_service_management_value(service_management):
    op.execute(
        config_table.update()
        .where(
            (config_table.c.name == op.inline_literal('service_management')) &
            (config_table.c.scope == op.inline_literal('rest'))
        )
        .values(value=service_management)
    )

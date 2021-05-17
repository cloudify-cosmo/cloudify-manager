"""Cloudify 6.0 to 6.1 DB migration

Revision ID: a31cb9e704d3
Revises: b92770a7b6ca
Create Date: 2021-05-17 15:10:26.844406

"""

from typing import NamedTuple

import sqlalchemy as sa

from manager_rest.storage import models_base


# revision identifiers, used by Alembic.
revision = 'a31cb9e704d3'
down_revision = 'b92770a7b6ca'
branch_labels = None
depends_on = None

config_table = sa.sql.table(
    'config',
    sa.sql.column('name', sa.Text),
    sa.sql.column('value', models_base.JSONString()),
    sa.sql.column('schema', models_base.JSONString()),
    sa.sql.column('is_editable', sa.Boolean),
    sa.sql.column('updated_at', models_base.UTCDateTime()),
    sa.sql.column('scope', sa.Text),
)
config_row = NamedTuple('ConfigRow', name=str, scope=str,
                        schema_6_0=str, schema_6_1=str)
CONFIG_SCHEMA_UPDATE = [
    config_row(name='broker_port', scope='agent',
               schema_6_0='{"type": "number", "minimum": 1, "maximum": 65535}',
               schema_6_1='{"type": "integer", "minimum": 1, '
                          '"maximum": 65535}'),
    config_row(name='max_workers', scope='agent',
               schema_6_0='{"type": "number", "minimum": 1}',
               schema_6_1='{"type": "integer", "minimum": 1}'),
    config_row(name='min_workers', scope='agent',
               schema_6_0='{"type": "number", "minimum": 1}',
               schema_6_1='{"type": "integer", "minimum": 1}'),
    config_row(name='max_workers', scope='mgmtworker',
               schema_6_0='{"type": "number", "minimum": 1}',
               schema_6_1='{"type": "integer", "minimum": 1}'),
    config_row(name='min_workers', scope='mgmtworker',
               schema_6_0='{"type": "number", "minimum": 1}',
               schema_6_1='{"type": "integer", "minimum": 1}'),
    config_row(name='blueprint_folder_max_files', scope='rest',
               schema_6_0='{"type": "number", "minimum": 0}',
               schema_6_1='{"type": "integer", "minimum": 0}'),
    config_row(name='default_page_size', scope='rest',
               schema_6_0='{"type": "number", "minimum": 1}',
               schema_6_1='{"type": "integer", "minimum": 1}'),
    config_row(name='failed_logins_before_account_lock', scope='rest',
               schema_6_0='{"type": "number", "minimum": 1}',
               schema_6_1='{"type": "integer", "minimum": 1}'),
    config_row(name='ldap_nested_levels', scope='rest',
               schema_6_0='{"type": "number", "minimum": 1}',
               schema_6_1='{"type": "integer", "minimum": 1}'),
    config_row(name='subgraph_retries', scope='workflow',
               schema_6_0='{"type": "number", "minimum": -1}',
               schema_6_1='{"type": "integer", "minimum": -1}'),
    config_row(name='task_retries', scope='workflow',
               schema_6_0='{"type": "number", "minimum": -1}',
               schema_6_1='{"type": "integer", "minimum": -1}'),
    config_row(name='task_retry_interval', scope='workflow',
               schema_6_0='{"type": "number", "minimum": -1}',
               schema_6_1='{"type": "integer", "minimum": -1}'),
]


def upgrade():
    _change_number_to_integer_in_config_schema()


def downgrade():
    _change_integer_to_number_in_config_schema()


def _change_number_to_integer_in_config_schema():
    for config_row in CONFIG_SCHEMA_UPDATE:
        config_table.update().\
            where(sa.and_(config_table.c.name == config_row.name,
                          config_table.c.scope == config_row.scope)).\
            values(schema=config_row.schema_6_1)


def _change_integer_to_number_in_config_schema():
    for config_row in CONFIG_SCHEMA_UPDATE:
        config_table.update().\
            where(sa.and_(config_table.c.name == config_row.name,
                          config_table.c.scope == config_row.scope)).\
            values(schema=config_row.schema_6_0)

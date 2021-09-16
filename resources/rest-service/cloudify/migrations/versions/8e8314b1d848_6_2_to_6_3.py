"""Cloudify 6.2 to 6.3 DB migration

Revision ID: 8e8314b1d848
Revises: 03ad040e6f78
Create Date: 2021-08-30 16:11:00

"""
import sqlalchemy as sa
from alembic import op

from manager_rest.storage.models_base import JSONString, UTCDateTime

# revision identifiers, used by Alembic.
revision = '8e8314b1d848'
down_revision = '03ad040e6f78'
branch_labels = None
depends_on = None


TABLES_TO_AUDIT = [('agents', 'storage_id'),
                   ('blueprints', 'storage_id'),
                   ('blueprints_filters', 'storage_id'),
                   ('blueprints_labels', 'id'),
                   ('certificates', 'id'),
                   ('deployment_groups', 'storage_id'),
                   ('deployment_groups_labels', 'id'),
                   ('deployment_labels_dependencies', 'storage_id'),
                   ('deployment_modifications', 'storage_id'),
                   ('deployment_update_steps', 'storage_id'),
                   ('deployment_updates', 'storage_id'),
                   ('deployments', 'storage_id'),
                   ('deployments_filters', 'storage_id'),
                   ('deployments_labels', 'id'),
                   ('execution_groups', 'storage_id'),
                   ('execution_schedules', 'storage_id'),
                   ('executions', 'storage_id'),
                   ('groups', 'id'),
                   ('inter_deployment_dependencies', 'storage_id'),
                   ('licenses', 'id'),
                   ('maintenance_mode', 'id'),
                   ('managers', 'id'),
                   ('node_instances', 'storage_id'),
                   ('nodes', 'storage_id'),
                   ('operations', 'storage_id'),
                   ('permissions', 'id'),
                   ('plugins', 'storage_id'),
                   ('plugins_states', 'storage_id'),
                   ('plugins_updates', 'storage_id'),
                   ('roles', 'id'),
                   ('secrets', 'storage_id'),
                   ('sites', 'storage_id'),
                   ('snapshots', 'storage_id'),
                   ('tasks_graphs', 'storage_id'),
                   ('tenants', 'id'),
                   ('usage_collector', 'id'),
                   ('users', 'id')]

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
    _drop_audit_log_creator_or_user_not_null_constraint()
    _create_functions_write_audit_log()
    _create_audit_triggers()
    _add_config_manager_service_log()
    _add_audit_log_indexes()
    _add_audit_log_notify()


def downgrade():
    _drop_audit_log_notify()
    _drop_audit_log_indexes()
    _drop_config_manager_service_log()
    _drop_audit_triggers()
    _drop_functions_write_audit_log()


# flake8: noqa
def _create_functions_write_audit_log():
    op.execute("""
    CREATE OR REPLACE FUNCTION audit_username() RETURNS TEXT AS $$
        BEGIN
            RETURN current_setting('audit.username');
        EXCEPTION WHEN syntax_error_or_access_rule_violation THEN
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;


    CREATE OR REPLACE FUNCTION audit_execution_id() RETURNS TEXT AS $$
        BEGIN
            RETURN current_setting('audit.execution_id');
        EXCEPTION WHEN syntax_error_or_access_rule_violation THEN
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;


    CREATE OR REPLACE FUNCTION write_audit_log_storage_id() RETURNS TRIGGER AS $$
        DECLARE
            _table TEXT := TG_ARGV[0]::TEXT;
            _user TEXT := public.audit_username();
            _execution_id TEXT := public.audit_execution_id();
        BEGIN
            IF (TG_OP = 'INSERT') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW._storage_id, 'create', _user, _execution_id, now());
            ELSEIF (TG_OP = 'UPDATE') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW._storage_id, 'update', _user, _execution_id, now());
            ELSEIF (TG_OP = 'DELETE') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, OLD._storage_id, 'delete', _user, _execution_id, now());
            END IF;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;


    CREATE OR REPLACE FUNCTION write_audit_log_id() RETURNS TRIGGER AS $$
        DECLARE
            _table TEXT := TG_ARGV[0]::TEXT;
            _user TEXT := public.audit_username();
            _execution_id TEXT := public.audit_execution_id();
        BEGIN
            IF (TG_OP = 'INSERT') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW.id, 'create', _user, _execution_id, now());
            ELSEIF (TG_OP = 'UPDATE') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW.id, 'update', _user, _execution_id, now());
            ELSEIF (TG_OP = 'DELETE') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, OLD.id, 'delete', _user, _execution_id, now());
            END IF;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;

    CREATE OR REPLACE FUNCTION write_audit_log_for_events_logs() RETURNS TRIGGER AS $$
        DECLARE
            _table TEXT := TG_ARGV[0]::TEXT;
            _user TEXT := public.audit_username();
            _execution_id TEXT := public.audit_execution_id();
        BEGIN
            IF (_execution_id IS NOT NULL) THEN
                RETURN NULL;
            END IF;
            IF (TG_OP = 'INSERT') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW._storage_id, 'create', _user, _execution_id, now());
            ELSEIF (TG_OP = 'UPDATE') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW._storage_id, 'update', _user, _execution_id, now());
            ELSEIF (TG_OP = 'DELETE') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, OLD._storage_id, 'delete', _user, _execution_id, now());
            END IF;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;""")


def _drop_functions_write_audit_log():
    op.execute("""DROP FUNCTION write_audit_log_for_events_logs();""")
    op.execute("""DROP FUNCTION write_audit_log_id();""")
    op.execute("""DROP FUNCTION write_audit_log_storage_id();""")
    op.execute("""DROP FUNCTION audit_execution_id();""")
    op.execute("""DROP FUNCTION audit_username();""")


# flake8: noqa
def _create_audit_triggers():
    for table_name, id_field in TABLES_TO_AUDIT:
        op.execute(f"""
            CREATE TRIGGER audit_{table_name}
            AFTER INSERT OR UPDATE OR DELETE ON {table_name} FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_{id_field}('{table_name}');""")
    for table_name in ['events', 'logs']:
        op.execute(f"""
            CREATE TRIGGER audit_{table_name}
            AFTER INSERT OR UPDATE OR DELETE ON {table_name} FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_for_events_logs('{table_name}');""")


def _drop_audit_triggers():
    for table_name, _ in TABLES_TO_AUDIT:
        op.execute(f"""DROP TRIGGER audit_{table_name} ON {table_name};""")
    for table_name in ['events', 'logs']:
        op.execute(f"""DROP TRIGGER audit_{table_name} ON {table_name};""")


def _drop_audit_log_creator_or_user_not_null_constraint():
    op.execute('ALTER TABLE audit_log '
               'DROP CONSTRAINT IF EXISTS audit_log_creator_or_user_not_null;')


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


def _add_audit_log_indexes():
    op.create_index(
        op.f('audit_log_creator_name_idx'),
        'audit_log', ['creator_name'],
        unique=False)
    op.create_index(
        op.f('audit_log_execution_id_idx'),
        'audit_log', ['execution_id'],
        unique=False)


def _drop_audit_log_indexes():
    op.drop_index(op.f('audit_log_creator_name_idx'), table_name='audit_log')
    op.drop_index(op.f('audit_log_execution_id_idx'), table_name='audit_log')


# flake8: noqa
def _add_audit_log_notify():
    op.execute("""CREATE OR REPLACE FUNCTION notify_new_audit_log() RETURNS TRIGGER AS $$
        BEGIN
            PERFORM pg_notify(
                'audit_log_inserted'::text,
                 row_to_json(NEW)::text
            );
            return NEW;
        END;
    $$ LANGUAGE plpgsql;""")
    op.execute("""CREATE TRIGGER audit_log_inserted
                  AFTER INSERT ON audit_log FOR EACH ROW
                  EXECUTE PROCEDURE notify_new_audit_log();""")


def _drop_audit_log_notify():
    op.execute("""DROP FUNCTION notify_new_audit_log();""")
    op.execute("""DROP TRIGGER audit_log_inserted ON audit_log;""")

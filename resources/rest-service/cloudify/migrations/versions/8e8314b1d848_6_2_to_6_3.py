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
    _add_max_concurrent_config()
    _add_system_properties_column()
    _add_plugins_labels_and_tags_columns()
    _add_deployment_resource_tags_column()
    _add_usage_collector_columns()
    _create_usage_collector_triggers()


def downgrade():
    # _drop_usage_collector_triggers()
    # _drop_usage_collector_columns()
    _drop_deployment_resource_tags_column()
    _drop_plugins_labels_and_tags_columns()
    _drop_system_properties_column()
    _drop_max_concurrent_config()
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


def _add_audit_log_notify():
    op.execute("""CREATE OR REPLACE FUNCTION notify_new_audit_log()
        RETURNS TRIGGER AS $$
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
    op.execute("""DROP TRIGGER audit_log_inserted ON audit_log;""")
    op.execute("""DROP FUNCTION notify_new_audit_log();""")


def _add_max_concurrent_config():
    op.bulk_insert(
        config_table,
        [
            dict(
                name='max_concurrent_workflows',
                value=20,
                scope='rest',
                schema={'type': 'number', 'minimum': 1, 'maximum': 1000},
                is_editable=True
            ),
        ]
    )


def _drop_max_concurrent_config():
    op.execute(
        config_table
        .delete()
        .where(
            (config_table.c.name == op.inline_literal(
                'max_concurrent_workflows')) &  # NOQA
            (config_table.c.scope == op.inline_literal('rest'))
        )
    )


def _add_system_properties_column():
    op.add_column(
        'node_instances',
        sa.Column('system_properties', JSONString()),
    )


def _drop_system_properties_column():
    op.drop_column('node_instances', 'system_properties')


def _add_plugins_labels_and_tags_columns():
    op.add_column(
        'plugins',
        sa.Column('blueprint_labels', JSONString()),
    )
    op.add_column(
        'plugins',
        sa.Column('labels', JSONString()),
    )
    op.add_column(
        'plugins',
        sa.Column('resource_tags', JSONString()),
    )


def _drop_plugins_labels_and_tags_columns():
    op.drop_column('plugins', 'blueprint_labels')
    op.drop_column('plugins', 'labels')
    op.drop_column('plugins', 'resource_tags')


def _add_deployment_resource_tags_column():
    op.add_column(
        'deployments',
        sa.Column('resource_tags', JSONString()),
    )


def _drop_deployment_resource_tags_column():
    op.drop_column('deployments', 'resource_tags')


def _add_usage_collector_columns():
    op.add_column('usage_collector', sa.Column('max_deployments',
                                               sa.Integer(),
                                               nullable=False,
                                               server_default="0"))
    op.add_column('usage_collector', sa.Column('max_blueprints',
                                               sa.Integer(),
                                               nullable=False,
                                               server_default="0"))
    op.add_column('usage_collector', sa.Column('max_users',
                                               sa.Integer(),
                                               nullable=False,
                                               server_default="0"))
    op.add_column('usage_collector', sa.Column('max_tenants',
                                               sa.Integer(),
                                               nullable=False,
                                               server_default="0"))
    op.add_column('usage_collector', sa.Column('total_deployments',
                                               sa.Integer(),
                                               nullable=False,
                                               server_default="0"))
    op.add_column('usage_collector', sa.Column('total_blueprints',
                                               sa.Integer(),
                                               nullable=False,
                                               server_default="0"))
    op.add_column('usage_collector', sa.Column('total_executions',
                                               sa.Integer(),
                                               nullable=False,
                                               server_default="0"))
    op.add_column('usage_collector', sa.Column('total_logins',
                                               sa.Integer(),
                                               nullable=False,
                                               server_default="0"))
    op.add_column('usage_collector', sa.Column('total_logged_in_users',
                                               sa.Integer(),
                                               nullable=False,
                                               server_default="0"))


def _drop_usage_collector_columns():
    op.drop_column('usage_collector', 'total_logged_in_users')
    op.drop_column('usage_collector', 'total_logins')
    op.drop_column('usage_collector', 'total_executions')
    op.drop_column('usage_collector', 'total_blueprints')
    op.drop_column('usage_collector', 'total_deployments')
    op.drop_column('usage_collector', 'max_tenants')
    op.drop_column('usage_collector', 'max_users')
    op.drop_column('usage_collector', 'max_blueprints')
    op.drop_column('usage_collector', 'max_deployments')


def _create_usage_collector_triggers():
    op.execute("""
    CREATE FUNCTION increase_deployments_max() RETURNS TRIGGER AS $$
        DECLARE
            _count_deployments INTEGER;
        BEGIN
            SELECT COUNT(*) INTO _count_deployments FROM deployments; 
            UPDATE usage_collector SET max_deployments = _count_deployments 
            WHERE _count_deployments > max_deployments;
            RETURN NULL; 
        END;
    $$ LANGUAGE plpgsql;
    
    CREATE FUNCTION increase_blueprints_max() RETURNS TRIGGER AS $$
        DECLARE
            _count_blueprints INTEGER;
        BEGIN
            SELECT COUNT(*) INTO _count_blueprints FROM blueprints; 
            UPDATE usage_collector SET max_blueprints = _count_blueprints 
            WHERE _count_blueprints > max_blueprints;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql; 
    
    CREATE FUNCTION increase_users_max() RETURNS TRIGGER AS $$
        DECLARE
            _count_users INTEGER;
        BEGIN
            SELECT COUNT(*) INTO _count_users FROM users; 
            UPDATE usage_collector SET max_users = _count_users 
            WHERE _count_users > max_users;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql; 
    
    CREATE FUNCTION increase_tenants_max() RETURNS TRIGGER AS $$
        DECLARE
            _count_tenants INTEGER;
        BEGIN
            SELECT COUNT(*) INTO _count_tenants FROM tenants; 
            UPDATE usage_collector SET max_tenants = _count_tenants 
            WHERE _count_tenants > max_tenants;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql; 

    CREATE FUNCTION increase_deployments_total() RETURNS TRIGGER AS $$
        BEGIN
            UPDATE usage_collector
            SET total_deployments = total_deployments + 1;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;

    CREATE FUNCTION increase_blueprints_total() RETURNS TRIGGER AS $$
        BEGIN
            UPDATE usage_collector SET total_blueprints = total_blueprints + 1;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;
    
    CREATE FUNCTION increase_executions_total() RETURNS TRIGGER AS $$
        BEGIN
            UPDATE usage_collector SET total_executions = total_executions + 1;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql; 
    
    CREATE FUNCTION increase_logins_total() RETURNS TRIGGER AS $$
        BEGIN
            UPDATE usage_collector SET total_logins = total_logins + 1;
            IF (OLD.last_login_at IS NULL)
            AND NOT (NEW.last_login_at IS NULL) THEN
                UPDATE usage_collector 
                SET total_logged_in_users = total_logged_in_users + 1;
            END IF;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql; 

    CREATE TRIGGER increase_deployments_max
    AFTER INSERT ON deployments FOR EACH STATEMENT
    EXECUTE PROCEDURE increase_deployments_max();

    CREATE TRIGGER increase_blueprints_max
    AFTER INSERT ON blueprints FOR EACH STATEMENT
    EXECUTE PROCEDURE increase_blueprints_max();

    CREATE TRIGGER increase_users_max 
    AFTER INSERT ON users FOR EACH STATEMENT
    EXECUTE PROCEDURE increase_users_max();

    CREATE TRIGGER increase_tenants_max 
    AFTER INSERT ON tenants FOR EACH STATEMENT
    EXECUTE PROCEDURE increase_tenants_max();

    CREATE TRIGGER increase_deployments_total
    AFTER INSERT ON deployments FOR EACH ROW
    EXECUTE PROCEDURE increase_deployments_total();

    CREATE TRIGGER increase_blueprints_total
    AFTER INSERT ON blueprints FOR EACH ROW
    EXECUTE PROCEDURE increase_blueprints_total();

    CREATE TRIGGER increase_executions_total 
    AFTER INSERT ON executions FOR EACH ROW
    EXECUTE PROCEDURE increase_executions_total();
    
    CREATE TRIGGER increase_logins_total 
    AFTER UPDATE OF last_login_at ON users FOR EACH ROW
    EXECUTE PROCEDURE increase_logins_total();
    """)


def _drop_usage_collector_triggers():
    op.execute("""
    DROP TRIGGER increase_deployments_max ON deployments;
    DROP TRIGGER increase_blueprints_max ON blueprints;
    DROP TRIGGER increase_users_max ON users;
    DROP TRIGGER increase_tenants_max ON tenants;
    DROP TRIGGER increase_deployments_total ON deployments;
    DROP TRIGGER increase_blueprints_total ON blueprints;
    DROP TRIGGER increase_executions_total ON executions;
    DROP TRIGGER increase_logins_total ON users;

    DROP FUNCTION increase_deployments_max();
    DROP FUNCTION increase_blueprints_max();
    DROP FUNCTION increase_users_max();
    DROP FUNCTION increase_tenants_max();
    DROP FUNCTION increase_deployments_total();
    DROP FUNCTION increase_blueprints_total();
    DROP FUNCTION increase_executions_total();
    DROP FUNCTION increase_logins_total();
    """)

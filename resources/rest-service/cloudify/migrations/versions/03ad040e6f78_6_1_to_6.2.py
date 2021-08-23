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

audit_operation = sa.Enum(
    'create', 'update', 'delete',
    name='audit_operation',
)


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


def upgrade():
    _create_audit_log_table()
    _create_functions_write_audit_log()
    _create_audit_triggers()


def downgrade():
    _drop_audit_triggers()
    _drop_functions_write_audit_log()
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
            IF (SELECT audit_username() IS NULL) THEN
                RETURN 'administrative task';
            END IF;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;


    CREATE OR REPLACE FUNCTION write_audit_log_storage_id() RETURNS TRIGGER AS $$
        DECLARE
            _table TEXT := TG_ARGV[0]::TEXT;
            _user TEXT := audit_username();
            _execution_id TEXT := audit_execution_id();
        BEGIN
            IF (TG_OP = 'INSERT') THEN
                INSERT INTO audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW._storage_id, 'create', _user, _execution_id, now());
                RETURN NEW;
            ELSEIF (TG_OP = 'UPDATE') THEN
                INSERT INTO audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW._storage_id, 'update', _user, _execution_id, now());
                RETURN NEW;
            ELSEIF (TG_OP = 'DELETE') THEN
                INSERT INTO audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, OLD._storage_id, 'delete', _user, _execution_id, now());
                RETURN OLD;
            END IF;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;


    CREATE OR REPLACE FUNCTION write_audit_log_id() RETURNS TRIGGER AS $$
        DECLARE
            _table TEXT := TG_ARGV[0]::TEXT;
            _user TEXT := audit_username();
            _execution_id TEXT := audit_execution_id();
        BEGIN
            IF (TG_OP = 'INSERT') THEN
                INSERT INTO audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW.id, 'create', _user, _execution_id, now());
                RETURN NEW;
            ELSEIF (TG_OP = 'UPDATE') THEN
                INSERT INTO audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW.id, 'update', _user, _execution_id, now());
                RETURN NEW;
            ELSEIF (TG_OP = 'DELETE') THEN
                INSERT INTO audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, OLD.id, 'delete', _user, _execution_id, now());
                RETURN OLD;
            END IF;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;""")


def _drop_functions_write_audit_log():
    op.execute("""DROP FUNCTION write_audit_log();""")


def _create_audit_triggers():
    for table_name, id_field in TABLES_TO_AUDIT:
        op.execute(f"""
            CREATE TRIGGER audit_{table_name}
            AFTER INSERT OR UPDATE OR DELETE ON {table_name} FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_{id_field}('{table_name}');""")


def _drop_audit_triggers():
    for table_name, _ in TABLES_TO_AUDIT:
        op.execute(f"""DROP TRIGGER audit_{table_name} ON {table_name};""")

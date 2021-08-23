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


TABLES_TO_AUDIT = ['agents',
                   'blueprints',
                   'blueprints_filter',
                   'blueprints_labels',
                   'certificates',
                   'config',
                   'db_nodes',
                   'deployment_groups',
                   'deployment_groups_deployments',
                   'deployment_groups_labels',
                   'deployment_labels_dependencies',
                   'deployment_modifications',
                   'deployment_update_steps',
                   'deployment_updates',
                   'deployments',
                   'deployments_filters',
                   'deployments_labels',
                   'execution_groups',
                   'execution_groups_executions',
                   'execution_schedules',
                   'executions',
                   'groups',
                   'groups_roles',
                   'groups_tenants',
                   'inter_deployment_dependencies',
                   'licenses',
                   'maintenance_mode',
                   'managers',
                   'node_instances',
                   'nodes',
                   'operations',
                   'permissions',
                   'plugins',
                   'plugins_states',
                   'plugins_updates',
                   'provider_context',
                   'rabbitmq_brokers',
                   'roles',
                   'secretes',
                   'sites',
                   'snapshots',
                   'tasks_graphs',
                   'tenants',
                   'usage_collector',
                   'users',
                   'users_groups',
                   'users_roles',
                   'users_tenants']


def upgrade():
    _create_audit_log_table()
    _create_function_write_audit_log()
    _create_audit_triggers()


def downgrade():
    _drop_audit_triggers()
    _drop_function_write_audit_log()
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
def _create_function_write_audit_log():
    op.execute("""
        CREATE OR REPLACE FUNCTION write_audit_log() RETURNS TRIGGER AS $func$
        DECLARE
            _table TEXT := TG_ARGV[0]::TEXT;
            _id INTEGER;`
            _user TEXT;
            _execution TEXT;
        BEGIN
            BEGIN
                SELECT current_setting('audit.username') INTO _user;
            EXCEPTION WHEN syntax_error_or_access_rule_violation THEN
                _user = NULL;
            END;
            BEGIN
                SELECT current_setting('audit.execution_id') INTO _execution;
            EXCEPTION WHEN syntax_error_or_access_rule_violation THEN
                _execution = NULL;
            END;
            IF (TG_OP = 'DELETE') THEN
                IF (_table = 'blueprints_labels') THEN
                    _id = OLD.id;
                ELSE
                    _id = OLD._storage_id;
                END IF;
                INSERT INTO audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, _id, 'delete', _user, _execution, now());
                RETURN OLD;
            ELSE
                IF (_table = 'blueprints_labels') THEN
                    _id = NEW.id;
                ELSE
                    _id = NEW._storage_id;
                END IF;
                IF (TG_OP = 'UPDATE') THEN
                    INSERT INTO audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                        VALUES (_table, _id, 'update', _user, _execution, now());
                    RETURN NEW;
                ELSIF (TG_OP = 'INSERT') THEN
                    INSERT INTO audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                        VALUES (_table, _id, 'create', _user, _execution, now());
                    RETURN NEW;
                END IF;
            END IF;
            RETURN NULL;
        END;
        $func$ LANGUAGE plpgsql;""")


def _drop_function_write_audit_log():
    op.execute("""DROP FUNCTION write_audit_log();""")


def _create_audit_triggers():
    for table_name in TABLES_TO_AUDIT:
        op.execute(f"""
            CREATE TRIGGER audit_{table_name}
            AFTER INSERT OR UPDATE OR DELETE ON {table_name}
            FOR EACH ROW EXECUTE PROCEDURE write_audit_log('{table_name}');""")


def _drop_audit_triggers():
    for table_name in TABLES_TO_AUDIT:
        op.execute(f"""DROP TRIGGER audit_{table_name} ON {table_name};""")

"""5_2 to 5_3

- Create blueprints_labels table
- Create deployment labels dependencies table
- Apply some modification to the deployments labels table
- Split the `filters` table to `deployments_filters` and `blueprints_filters`
- Add installation_status to the deployment table
- Add deployment_status to the deployment table
- Add latest execution FK to the deployment table
- Add statuses and counters for sub-services and sub-environments

Revision ID: 396303c07e35
Revises: 9d261e90b1f3
Create Date: 2021-02-15 12:02:22.089135

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from cloudify.models_states import VisibilityState
from manager_rest.storage.models_base import UTCDateTime, JSONString

# revision identifiers, used by Alembic.
revision = '396303c07e35'
down_revision = '9d261e90b1f3'
branch_labels = None
depends_on = None

installation_status = sa.Enum(
    'active',
    'inactive',
    name='installation_status'
)

deployment_status = sa.Enum(
    'good',
    'in_progress',
    'requires_attention',
    name='deployment_status'
)

VISIBILITY_ENUM = postgresql.ENUM(
    *VisibilityState.STATES,
    name='visibility_states',
    create_type=False
)


def upgrade():
    _create_blueprints_labels_table()
    _modify_deployments_labels_table()
    _modify_execution_schedules_table()
    _add_specialized_execution_fk()
    _create_filters_tables()
    _add_deployment_statuses()
    _add_execgroups_concurrency()
    _add_executions_columns()
    _create_deployment_labels_dependencies_table()
    _add_deployment_sub_statuses_and_counters()
    _create_depgroups_labels_table()
    _modify_users_table()


def downgrade():
    _revert_changes_to_users_table()
    _drop_depgroups_labels_table()
    _drop_deployment_sub_statuses_and_counters()
    _drop_deployment_labels_dependencies_table()
    _drop_execgroups_concurrency()
    _drop_deployment_statuses()
    _revert_filters_modifications()
    _drop_specialized_execution_fk()
    _revert_changes_to_execution_schedules_table()
    _revert_changes_to_deployments_labels_table()
    _drop_blueprints_labels_table()
    _drop_execution_columns()
    _drop_deployment_statuses_enum_types()


def _add_deployment_sub_statuses_and_counters():
    op.add_column(
        'deployments',
        sa.Column(
            'sub_environments_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
        )
    )
    op.add_column(
        'deployments',
        sa.Column(
            'sub_environments_status',
            sa.Enum(
                'good',
                'in_progress',
                'require_attention',
                name='deployment_status'
            ),
            nullable=True
        )
    )
    op.add_column(
        'deployments',
        sa.Column(
            'sub_services_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
        )
    )
    op.add_column(
        'deployments',
        sa.Column(
            'sub_services_status',
            sa.Enum('good',
                    'in_progress',
                    'require_attention',
                    name='deployment_status'
                    ),
            nullable=True
        )
    )


def _create_deployment_labels_dependencies_table():
    op.create_table(
        'deployment_labels_dependencies',
        sa.Column('_storage_id', sa.Integer(), autoincrement=True,
                  nullable=False),
        sa.Column('id', sa.Text(), nullable=True),
        sa.Column('visibility', VISIBILITY_ENUM, nullable=True),
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('_source_deployment', sa.Integer(),
                  nullable=False),
        sa.Column('_target_deployment', sa.Integer(),
                  nullable=False),
        sa.Column('_tenant_id', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['_creator_id'], ['users.id'],
            name=op.f('deployment_labels_dependencies__creator_id_fkey'),
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['_tenant_id'], ['tenants.id'],
            name=op.f('deployment_labels_dependencies__tenant_id_fkey'),
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['_source_deployment'], ['deployments._storage_id'],
            name=op.f(
                'deployment_labels_dependencies__source_deployment_fkey'
            ), ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['_target_deployment'], ['deployments._storage_id'],
            name=op.f(
                'deployment_labels_dependencies__target_deployment_fkey'
            ), ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint(
            '_storage_id', name=op.f('deployment_labels_dependencies_pkey')
        ),

        sa.UniqueConstraint(
            '_source_deployment',
            '_target_deployment',
            name=op.f(
                'deployment_labels_dependencies__source_deployment_key'
            )
        )
    )
    op.create_index(
        op.f('deployment_labels_dependencies__creator_id_idx'),
        'deployment_labels_dependencies', ['_creator_id'], unique=False
    )
    op.create_index(
        op.f('deployment_labels_dependencies__tenant_id_idx'),
        'deployment_labels_dependencies', ['_tenant_id'], unique=False
    )
    op.create_index(
        op.f('deployment_labels_dependencies_created_at_idx'),
        'deployment_labels_dependencies', ['created_at'], unique=False
    )
    op.create_index(
        op.f('deployment_labels_dependencies_id_idx'),
        'deployment_labels_dependencies', ['id'], unique=False
    )
    op.create_index(
        op.f('deployment_labels_dependencies__source_deployment_idx'),
        'deployment_labels_dependencies', ['_source_deployment'],
        unique=False
    )
    op.create_index(
        op.f('deployment_labels_dependencies__target_deployment_idx'),
        'deployment_labels_dependencies', ['_target_deployment'],
        unique=False
    )
    op.create_index(
        op.f('deployment_labels_dependencies_visibility_idx'),
        'deployment_labels_dependencies', ['visibility'], unique=False
    )


def _add_deployment_statuses():
    installation_status.create(op.get_bind())
    deployment_status.create(op.get_bind())
    op.add_column(
        'deployments',
        sa.Column(
            'installation_status',
            type_=installation_status,
            nullable=True
        )
    )
    op.add_column(
        'deployments',
        sa.Column(
            'deployment_status',
            type_=deployment_status,
            nullable=True
        )
    )


def _add_specialized_execution_fk():
    """Add FKs that point to special executions:
    - the upload_blueprint execution for a blueprint
    - the create-dep-env execution for a deployment
    """
    op.add_column(
        'blueprints',
        sa.Column('_upload_execution_fk', sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f('blueprints__upload_execution_fk_idx'),
        'blueprints',
        ['_upload_execution_fk'],
        unique=False
    )
    op.create_foreign_key(
        op.f('blueprints__upload_execution_fk_fkey'),
        'blueprints',
        'executions',
        ['_upload_execution_fk'],
        ['_storage_id'],
        ondelete='SET NULL',
        deferrable=True,
        initially='DEFERRED',
    )
    op.add_column(
        'deployments',
        sa.Column('_create_execution_fk', sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f('deployments__create_execution_fk_idx'),
        'deployments',
        ['_create_execution_fk'],
        unique=False
    )
    op.create_foreign_key(
        op.f('deployments__create_execution_fk_fkey'),
        'deployments',
        'executions',
        ['_create_execution_fk'],
        ['_storage_id'],
        ondelete='SET NULL',
        deferrable=True,
        initially='DEFERRED',
    )

    op.add_column(
        'deployments',
        sa.Column('_latest_execution_fk', sa.Integer(), nullable=True))

    op.create_index(
        op.f('deployments__latest_execution_fk_idx'),
        'deployments',
        ['_latest_execution_fk'],
        unique=True
    )

    op.create_foreign_key(
        op.f('deployments__latest_execution_fk_fkey'),
        'deployments',
        'executions',
        ['_latest_execution_fk'],
        ['_storage_id'],
        ondelete='SET NULL',
        initially='DEFERRED',
        deferrable=True,
        use_alter=True
    )


def _drop_specialized_execution_fk():
    op.drop_constraint(
        op.f('deployments__latest_execution_fk_fkey'),
        'deployments',
        type_='foreignkey'
    )

    op.drop_index(
        op.f('deployments__latest_execution_fk_idx'),
        table_name='deployments'
    )

    op.drop_column(
        'deployments',
        '_latest_execution_fk'
    )

    op.drop_constraint(
        op.f('deployments__create_execution_fk_fkey'),
        'deployments',
        type_='foreignkey'
    )
    op.drop_index(
        op.f('deployments__create_execution_fk_idx'),
        table_name='deployments'
    )
    op.drop_column('deployments', '_create_execution_fk')

    op.drop_constraint(
        op.f('blueprints__upload_execution_fk_fkey'),
        'blueprints',
        type_='foreignkey'
    )
    op.drop_index(
        op.f('blueprints__upload_execution_fk_idx'),
        table_name='blueprints'
    )
    op.drop_column('blueprints', '_upload_execution_fk')


def _create_blueprints_labels_table():
    op.create_table(
        'blueprints_labels',
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('_labeled_model_fk', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['_creator_id'],
            ['users.id'],
            name=op.f('blueprints_labels__creator_id_fkey'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_labeled_model_fk'],
            ['blueprints._storage_id'],
            name=op.f('blueprints_labels__labeled_model_fk_fkey'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint(
            'id',
            name=op.f('blueprints_labels_pkey')),
        sa.UniqueConstraint(
            'key',
            'value',
            '_labeled_model_fk',
            name=op.f('blueprints_labels_key_key'))
    )
    op.create_index(op.f('blueprints_labels__creator_id_idx'),
                    'blueprints_labels',
                    ['_creator_id'],
                    unique=False)
    op.create_index(op.f('blueprints_labels__labeled_model_fk_idx'),
                    'blueprints_labels',
                    ['_labeled_model_fk'],
                    unique=False)
    op.create_index(op.f('blueprints_labels_created_at_idx'),
                    'blueprints_labels',
                    ['created_at'],
                    unique=False)
    op.create_index(op.f('blueprints_labels_key_idx'),
                    'blueprints_labels',
                    ['key'],
                    unique=False)
    op.create_index(op.f('blueprints_labels_value_idx'),
                    'blueprints_labels',
                    ['value'],
                    unique=False)


dl_table = sa.table(
    'deployments_labels',
    sa.Column('_labeled_model_fk'),
    sa.Column('_deployment_fk')
)


def _modify_deployments_labels_table():
    op.add_column('deployments_labels',
                  sa.Column('_labeled_model_fk', sa.Integer(), nullable=True))
    op.execute(
        dl_table
        .update()
        .where(dl_table.c._labeled_model_fk.is_(None))
        .values(_labeled_model_fk=dl_table.c._deployment_fk)
    )
    op.alter_column(
        'deployments_labels',
        '_labeled_model_fk',
        existing_type=sa.Integer(),
        nullable=False
    )

    op.drop_index('deployments_labels__deployment_fk_idx',
                  table_name='deployments_labels')
    op.drop_constraint('deployments_labels_key_key',
                       'deployments_labels',
                       type_='unique')
    op.create_unique_constraint(op.f('deployments_labels_key_key'),
                                'deployments_labels',
                                ['key', 'value', '_labeled_model_fk'])
    op.create_index(op.f('deployments_labels__labeled_model_fk_idx'),
                    'deployments_labels',
                    ['_labeled_model_fk'],
                    unique=False)
    op.drop_constraint('deployments_labels__deployment_fk',
                       'deployments_labels',
                       type_='foreignkey')
    op.create_foreign_key(op.f('deployments_labels__labeled_model_fk_fkey'),
                          'deployments_labels',
                          'deployments',
                          ['_labeled_model_fk'],
                          ['_storage_id'],
                          ondelete='CASCADE')
    op.drop_column('deployments_labels', '_deployment_fk')


def _revert_changes_to_deployments_labels_table():
    op.add_column('deployments_labels',
                  sa.Column('_deployment_fk',
                            sa.INTEGER(),
                            autoincrement=False))
    op.execute(
        dl_table
        .update()
        .values(_deployment_fk=dl_table.c._labeled_model_fk)
    )
    op.drop_constraint(op.f('deployments_labels__labeled_model_fk_fkey'),
                       'deployments_labels',
                       type_='foreignkey')
    op.create_foreign_key('deployments_labels__deployment_fk',
                          'deployments_labels',
                          'deployments',
                          ['_deployment_fk'],
                          ['_storage_id'],
                          ondelete='CASCADE')
    op.drop_index(op.f('deployments_labels__labeled_model_fk_idx'),
                  table_name='deployments_labels')
    op.drop_constraint(op.f('deployments_labels_key_key'),
                       'deployments_labels',
                       type_='unique')
    op.create_unique_constraint('deployments_labels_key_key',
                                'deployments_labels',
                                ['key', 'value', '_deployment_fk'])
    op.create_index('deployments_labels__deployment_fk_idx',
                    'deployments_labels',
                    ['_deployment_fk'],
                    unique=False)
    op.drop_column('deployments_labels', '_labeled_model_fk')


def _modify_execution_schedules_table():
    op.create_index('execution_schedules_id__deployment_fk_idx',
                    'execution_schedules',
                    ['id', '_deployment_fk', '_tenant_id'],
                    unique=True)
    op.create_unique_constraint(op.f('execution_schedules_id_key'),
                                'execution_schedules',
                                ['id', '_deployment_fk', '_tenant_id'])


def _revert_changes_to_execution_schedules_table():
    op.drop_constraint(op.f('execution_schedules_id_key'),
                       'execution_schedules', type_='unique')
    op.drop_index('execution_schedules_id__deployment_fk_idx',
                  table_name='execution_schedules')


def _drop_blueprints_labels_table():
    op.drop_index(op.f('blueprints_labels_value_idx'),
                  table_name='blueprints_labels')
    op.drop_index(op.f('blueprints_labels_key_idx'),
                  table_name='blueprints_labels')
    op.drop_index(op.f('blueprints_labels_created_at_idx'),
                  table_name='blueprints_labels')
    op.drop_index(op.f('blueprints_labels__labeled_model_fk_idx'),
                  table_name='blueprints_labels')
    op.drop_index(op.f('blueprints_labels__creator_id_idx'),
                  table_name='blueprints_labels')
    op.drop_table('blueprints_labels')


def _drop_deployment_statuses():
    op.drop_column('deployments', 'installation_status')
    op.drop_column('deployments', 'deployment_status')


def _create_filters_tables():
    op.create_table(
        'blueprints_filters',
        sa.Column('_storage_id',
                  sa.Integer(),
                  autoincrement=True,
                  nullable=False),
        sa.Column('id', sa.Text(), nullable=True),
        sa.Column('visibility', VISIBILITY_ENUM, nullable=True),
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('value', JSONString(), nullable=True),
        sa.Column('updated_at', UTCDateTime(), nullable=True),
        sa.Column('_tenant_id', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.Column('is_system_filter', sa.Boolean(), nullable=False,
                  server_default='f'),
        sa.ForeignKeyConstraint(
            ['_creator_id'],
            ['users.id'],
            name=op.f('blueprints_filters__creator_id_fkey'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_tenant_id'],
            ['tenants.id'],
            name=op.f('blueprints_filters__tenant_id_fkey'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint(
            '_storage_id',
            name=op.f('blueprints_filters_pkey'))
    )
    op.create_index(op.f('blueprints_filters__creator_id_idx'),
                    'blueprints_filters',
                    ['_creator_id'],
                    unique=False)
    op.create_index(op.f('blueprints_filters__tenant_id_idx'),
                    'blueprints_filters',
                    ['_tenant_id'],
                    unique=False)
    op.create_index(op.f('blueprints_filters_created_at_idx'),
                    'blueprints_filters',
                    ['created_at'],
                    unique=False)
    op.create_index('blueprints_filters_id__tenant_id_idx',
                    'blueprints_filters',
                    ['id', '_tenant_id'],
                    unique=True)
    op.create_index(op.f('blueprints_filters_id_idx'),
                    'blueprints_filters',
                    ['id'],
                    unique=False)
    op.create_index(op.f('blueprints_filters_visibility_idx'),
                    'blueprints_filters',
                    ['visibility'],
                    unique=False)
    op.create_index(op.f('blueprints_filters_is_system_filter_idx'),
                    'blueprints_filters',
                    ['is_system_filter'],
                    unique=False)

    op.create_table(
        'deployments_filters',
        sa.Column('_storage_id',
                  sa.Integer(),
                  autoincrement=True,
                  nullable=False),
        sa.Column('id', sa.Text(), nullable=True),
        sa.Column('visibility', VISIBILITY_ENUM, nullable=True),
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('value', JSONString(), nullable=True),
        sa.Column('updated_at', UTCDateTime(), nullable=True),
        sa.Column('_tenant_id', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.Column('is_system_filter', sa.Boolean(), nullable=False,
                  server_default='f'),
        sa.ForeignKeyConstraint(
            ['_creator_id'],
            ['users.id'],
            name=op.f('deployments_filters__creator_id_fkey'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_tenant_id'],
            ['tenants.id'],
            name=op.f('deployments_filters__tenant_id_fkey'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint(
            '_storage_id',
            name=op.f('deployments_filters_pkey'))
    )
    op.create_index(op.f('deployments_filters__creator_id_idx'),
                    'deployments_filters',
                    ['_creator_id'],
                    unique=False)
    op.create_index(op.f('deployments_filters__tenant_id_idx'),
                    'deployments_filters',
                    ['_tenant_id'],
                    unique=False)
    op.create_index(op.f('deployments_filters_created_at_idx'),
                    'deployments_filters',
                    ['created_at'],
                    unique=False)
    op.create_index('deployments_filters_id__tenant_id_idx',
                    'deployments_filters',
                    ['id', '_tenant_id'],
                    unique=True)
    op.create_index(op.f('deployments_filters_id_idx'),
                    'deployments_filters',
                    ['id'],
                    unique=False)
    op.create_index(op.f('deployments_filters_visibility_idx'),
                    'deployments_filters',
                    ['visibility'],
                    unique=False)
    op.create_index(op.f('deployments_filters_is_system_filter_idx'),
                    'deployments_filters',
                    ['is_system_filter'],
                    unique=False)

    op.drop_index('filters__creator_id_idx',
                  table_name='filters')
    op.drop_index('filters__tenant_id_idx',
                  table_name='filters')
    op.drop_index('filters_created_at_idx',
                  table_name='filters')
    op.drop_index('filters_id__tenant_id_idx',
                  table_name='filters')
    op.drop_index('filters_id_idx',
                  table_name='filters')
    op.drop_index('filters_visibility_idx',
                  table_name='filters')
    op.drop_table('filters')


def _revert_filters_modifications():
    op.create_table(
        'filters',
        sa.Column('_storage_id',
                  sa.INTEGER(),
                  autoincrement=True,
                  nullable=False),
        sa.Column('id', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('value', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('visibility',
                  VISIBILITY_ENUM,
                  autoincrement=False,
                  nullable=True),
        sa.Column('created_at',
                  UTCDateTime,
                  autoincrement=False,
                  nullable=False),
        sa.Column('updated_at',
                  UTCDateTime,
                  autoincrement=False,
                  nullable=True),
        sa.Column('_tenant_id',
                  sa.INTEGER(),
                  autoincrement=False,
                  nullable=False),
        sa.Column('_creator_id',
                  sa.INTEGER(),
                  autoincrement=False,
                  nullable=False),
        sa.ForeignKeyConstraint(
            ['_creator_id'],
            ['users.id'],
            name='filters__creator_id_fkey',
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_tenant_id'],
            ['tenants.id'],
            name='filters__tenant_id_fkey',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('_storage_id', name='filters_pkey')
    )
    op.create_index('filters_visibility_idx',
                    'filters',
                    ['visibility'],
                    unique=False)
    op.create_index('filters_id_idx',
                    'filters',
                    ['id'],
                    unique=False)
    op.create_index('filters_id__tenant_id_idx',
                    'filters',
                    ['id', '_tenant_id'],
                    unique=True)
    op.create_index('filters_created_at_idx',
                    'filters',
                    ['created_at'],
                    unique=False)
    op.create_index('filters__tenant_id_idx',
                    'filters',
                    ['_tenant_id'],
                    unique=False)
    op.create_index('filters__creator_id_idx',
                    'filters',
                    ['_creator_id'],
                    unique=False)

    op.drop_index(op.f('deployments_filters_visibility_idx'),
                  table_name='deployments_filters')
    op.drop_index(op.f('deployments_filters_id_idx'),
                  table_name='deployments_filters')
    op.drop_index('deployments_filters_id__tenant_id_idx',
                  table_name='deployments_filters')
    op.drop_index(op.f('deployments_filters_created_at_idx'),
                  table_name='deployments_filters')
    op.drop_index(op.f('deployments_filters__tenant_id_idx'),
                  table_name='deployments_filters')
    op.drop_index(op.f('deployments_filters__creator_id_idx'),
                  table_name='deployments_filters')
    op.drop_index(op.f('deployments_filters_is_system_filter_idx'),
                  table_name='deployments_filters')
    op.drop_table('deployments_filters')

    op.drop_index(op.f('blueprints_filters_visibility_idx'),
                  table_name='blueprints_filters')
    op.drop_index(op.f('blueprints_filters_id_idx'),
                  table_name='blueprints_filters')
    op.drop_index('blueprints_filters_id__tenant_id_idx',
                  table_name='blueprints_filters')
    op.drop_index(op.f('blueprints_filters_created_at_idx'),
                  table_name='blueprints_filters')
    op.drop_index(op.f('blueprints_filters__tenant_id_idx'),
                  table_name='blueprints_filters')
    op.drop_index(op.f('blueprints_filters__creator_id_idx'),
                  table_name='blueprints_filters')
    op.drop_index(op.f('blueprints_filters_is_system_filter_idx'),
                  table_name='blueprints_filters')
    op.drop_table('blueprints_filters')


def _add_execgroups_concurrency():
    op.add_column(
        'execution_groups',
        sa.Column(
            'concurrency',
            sa.Integer(),
            server_default='5',
            nullable=False
        )
    )


def _drop_execgroups_concurrency():
    op.drop_column('execution_groups', 'concurrency')


def _add_executions_columns():
    op.add_column(
        'executions',
        sa.Column('finished_operations', sa.Integer(), nullable=True)
    )
    op.add_column(
        'executions',
        sa.Column('total_operations', sa.Integer(), nullable=True)
    )
    op.add_column(
        'executions',
        sa.Column('resume', sa.Boolean(),
                  server_default='false', nullable=False)
    )


def _drop_execution_columns():
    op.drop_column('executions', 'total_operations')
    op.drop_column('executions', 'finished_operations')
    op.drop_column('executions', 'resume')


def _drop_deployment_labels_dependencies_table():
    op.drop_index(
        op.f('deployment_labels_dependencies_visibility_idx'),
        table_name='deployment_labels_dependencies'
    )
    op.drop_index(
        op.f('deployment_labels_dependencies__target_deployment_idx'),
        table_name='deployment_labels_dependencies'
    )
    op.drop_index(
        op.f('deployment_labels_dependencies__source_deployment_idx'),
        table_name='deployment_labels_dependencies'
    )
    op.drop_index(
        op.f('deployment_labels_dependencies_id_idx'),
        table_name='deployment_labels_dependencies'
    )
    op.drop_index(
        op.f('deployment_labels_dependencies_created_at_idx'),
        table_name='deployment_labels_dependencies'
    )
    op.drop_index(
        op.f('deployment_labels_dependencies__tenant_id_idx'),
        table_name='deployment_labels_dependencies'
    )
    op.drop_index(
        op.f('deployment_labels_dependencies__creator_id_idx'),
        table_name='deployment_labels_dependencies'
    )
    op.drop_table('deployment_labels_dependencies')


def _drop_deployment_sub_statuses_and_counters():
    op.drop_column('deployments', 'sub_services_status')
    op.drop_column('deployments', 'sub_services_count')
    op.drop_column('deployments', 'sub_environments_status')
    op.drop_column('deployments', 'sub_environments_count')


def _drop_deployment_statuses_enum_types():
    installation_status.drop(op.get_bind())
    deployment_status.drop(op.get_bind())


def _create_depgroups_labels_table():
    op.create_table(
        'deployment_groups_labels',
        sa.Column('created_at', UTCDateTime(), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('_labeled_model_fk', sa.Integer(), nullable=False),
        sa.Column('_creator_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['_creator_id'], ['users.id'],
            name=op.f('deployment_groups_labels__creator_id_fkey'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['_labeled_model_fk'], ['deployment_groups._storage_id'],
            name=op.f('deployment_groups_labels__labeled_model_fk_fkey'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint(
            'id', name=op.f('deployment_groups_labels_pkey')),
        sa.UniqueConstraint(
            'key', 'value', '_labeled_model_fk',
            name=op.f('deployment_groups_labels_key_key'))
    )
    op.create_index(
        op.f('deployment_groups_labels__creator_id_idx'),
        'deployment_groups_labels', ['_creator_id'], unique=False)
    op.create_index(
        op.f('deployment_groups_labels__labeled_model_fk_idx'),
        'deployment_groups_labels', ['_labeled_model_fk'], unique=False)
    op.create_index(
        op.f('deployment_groups_labels_created_at_idx'),
        'deployment_groups_labels', ['created_at'], unique=False)
    op.create_index(
        op.f('deployment_groups_labels_key_idx'),
        'deployment_groups_labels', ['key'], unique=False)
    op.create_index(
        op.f('deployment_groups_labels_value_idx'),
        'deployment_groups_labels', ['value'], unique=False)


def _drop_depgroups_labels_table():
    op.drop_index(
        op.f('deployment_groups_labels_value_idx'),
        table_name='deployment_groups_labels')
    op.drop_index(
        op.f('deployment_groups_labels_key_idx'),
        table_name='deployment_groups_labels')
    op.drop_index(
        op.f('deployment_groups_labels_created_at_idx'),
        table_name='deployment_groups_labels')
    op.drop_index(
        op.f('deployment_groups_labels__labeled_model_fk_idx'),
        table_name='deployment_groups_labels')
    op.drop_index(
        op.f('deployment_groups_labels__creator_id_idx'),
        table_name='deployment_groups_labels')
    op.drop_table('deployment_groups_labels')


def _modify_users_table():
    op.add_column(
        'users',
        sa.Column('show_getting_started',
                  sa.Boolean(),
                  nullable=False,
                  server_default='t')
    )
    op.add_column('users',
                  sa.Column('first_login_at', UTCDateTime(), nullable=True))


def _revert_changes_to_users_table():
    op.drop_column('users', 'first_login_at')
    op.drop_column('users', 'show_getting_started')

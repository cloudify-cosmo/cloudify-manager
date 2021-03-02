"""5_2 to 5_3

- Create blueprints_labels table
- Add installation_status to the deployment table
- Add deployment_status to the deployment table
- Add latest execution FK to the deployment table

Revision ID: 396303c07e35
Revises: 9d261e90b1f3
Create Date: 2021-02-15 12:02:22.089135

"""
from alembic import op
import sqlalchemy as sa

from manager_rest.storage.models_base import UTCDateTime

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


def upgrade():
    _create_blueprints_labels_table()
    _modify_deployments_labels_table()
    _modify_execution_schedules_table()
    _add_specialized_execution_fk()
    _modify_filters_table()
    _add_deployment_statuses()
    _add_execgroups_concurrency()


def downgrade():
    _drop_execgroups_concurrency()
    _drop_deployment_statuses()
    _revert_changes_to_deployments_labels_table()
    _drop_specialized_execution_fk()
    _revert_changes_to_execution_schedules_table()
    _revert_changes_to_deployments_labels_table()
    _drop_blueprints_labels_table()


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


def _modify_deployments_labels_table():
    op.add_column('deployments_labels',
                  sa.Column('_labeled_model_fk', sa.Integer(), nullable=False))
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


def _modify_filters_table():
    op.add_column('filters',
                  sa.Column('filtered_resource', sa.Text(), nullable=False))
    op.create_index(op.f('filters_filtered_resource_idx'),
                    'filters',
                    ['filtered_resource'],
                    unique=False)


def _revert_changes_to_deployments_labels_table():
    op.add_column('deployments_labels',
                  sa.Column('_deployment_fk',
                            sa.INTEGER(),
                            autoincrement=False,
                            nullable=False))
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
                    unique=False)
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


def _revert_changes_to_filters_table():
    op.drop_index(op.f('filters_filtered_resource_idx'), table_name='filters')
    op.drop_column('filters', 'filtered_resource')


def _drop_deployment_statuses():
    op.drop_column('deployments', 'installation_status')
    op.drop_column('deployments', 'deployment_status')

    installation_status.drop(op.get_bind())
    deployment_status.drop(op.get_bind())


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

"""<changes description>

Revision ID: 3483e421713d
Revises: 784a82cec07a
Create Date: 2017-12-27 12:29:26.302823

"""
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3483e421713d'
down_revision = '784a82cec07a'
branch_labels = None
depends_on = None

resource_tables = ['blueprints', 'plugins', 'secrets', 'snapshots', 'events',
                   'executions', 'logs', 'nodes', 'node_instances',
                   'deployments', 'deployment_modifications',
                   'deployment_updates', 'deployment_update_steps']
visibility_states = ['private', 'tenant', 'global']
DEFAULT_SYSTEM_ROLE_ID = 6


def upgrade():
    # Change the name and the type of the column resource_availability
    # to visibility
    visibility_enum = postgresql.ENUM(*visibility_states,
                                      name='visibility_states')
    op.execute(postgresql.base.CreateEnumType(visibility_enum))
    for table_name in resource_tables:
        op.alter_column(table_name,
                        'resource_availability',
                        new_column_name='visibility',
                        type_=visibility_enum,
                        postgresql_using='resource_availability::text::'
                                         'visibility_states')

    # Remove the enum resource_availability from postgres
    op.execute("DROP TYPE resource_availability;")


def downgrade():
    # Change the name and the type of the column visibility back
    # to resource_availability
    resource_availability = postgresql.ENUM(*visibility_states,
                                            name='resource_availability')
    op.execute(postgresql.base.CreateEnumType(resource_availability))
    for table_name in resource_tables:
        op.alter_column(table_name,
                        'visibility',
                        new_column_name='resource_availability',
                        type_=resource_availability,
                        postgresql_using='visibility::text::'
                                         'resource_availability')

    # Remove the enum visibility_states from postgres
    op.execute("DROP TYPE visibility_states;")

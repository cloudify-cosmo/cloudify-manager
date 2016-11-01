#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from flask_security import SQLAlchemyUserDatastore, UserMixin, RoleMixin

from manager_rest.deployment_update.constants import ACTION_TYPES, ENTITY_TYPES
from manager_rest.constants import (ADMINISTRATOR_ROLES,
                                    SYSTEM_ADMIN_ROLE,
                                    TENANT_ADMIN_ROLE,
                                    DEFAULT_ROLE,
                                    VIEWER_ROLE,
                                    SUSPENDED_ROLE)

from .models_base import (db,
                          SQLModelBase,
                          SQLResource,
                          UTCDateTime)
from .relationships import (one_to_many_relationship,
                            many_to_many_relationship,
                            foreign_key,
                            tenants_groups_table,
                            roles_users_table,
                            groups_users_table,
                            tenants_users_table)
from .models_states import (DeploymentModificationState,
                            SnapshotState,
                            ExecutionState)


#  region Users, Groups, Tenants
class Tenant(SQLModelBase):
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, index=True)

    def _get_unique_id(self):
        return 'name', self.name

    def to_dict(self, suppress_error=False):
        tenant_dict = super(Tenant, self).to_dict(suppress_error)
        all_groups_names = [group.name for group in self.groups.all()]
        all_users_names = [user.username for user in self.users.all()]
        tenant_dict['groups'] = all_groups_names
        tenant_dict['users'] = all_users_names
        return tenant_dict


class Group(SQLModelBase):
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, nullable=False, index=True)

    def _get_unique_id(self):
        return 'name', self.name

    tenants = many_to_many_relationship(
        other_table_class_name='Tenant',
        connecting_table=tenants_groups_table,
        back_reference_name='groups'
    )

    def to_dict(self, suppress_error=False):
        group_dict = super(Group, self).to_dict(suppress_error)
        group_dict['tenants'] = [tenant.name for tenant in self.tenants]
        group_dict['users'] = [user.username for user in self.users]
        return group_dict


class User(SQLModelBase, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(255), index=True, unique=True)

    active = db.Column(db.Boolean)
    created_at = db.Column(UTCDateTime)
    email = db.Column(db.String(255), index=True)
    first_name = db.Column(db.String(255))
    last_login_at = db.Column(UTCDateTime, index=True)
    last_name = db.Column(db.String(255))
    password = db.Column(db.String(255))

    def _get_unique_id(self):
        return 'username', self.username

    roles = many_to_many_relationship(
        other_table_class_name='Role',
        connecting_table=roles_users_table,
        back_reference_name='users'
    )

    groups = many_to_many_relationship(
        other_table_class_name='Group',
        connecting_table=groups_users_table,
        back_reference_name='users'
    )

    tenants = many_to_many_relationship(
        other_table_class_name='Tenant',
        connecting_table=tenants_users_table,
        back_reference_name='users'
    )

    def get_all_tenants(self):
        """Return all tenants associated with a user - either directly, or
        via a group the user is in

        Note: recursive membership in groups is currently not supported
        """
        tenant_list = self.tenants
        for group in self.groups:
            for tenant in group.tenants:
                tenant_list.append(tenant)

        return list(set(tenant_list))

    def to_dict(self, suppress_error=False):
        user_dict = super(User, self).to_dict(suppress_error)
        all_tenants = [tenant.name for tenant in self.get_all_tenants()]
        user_dict['tenants'] = all_tenants
        user_dict['groups'] = [group.name for group in self.groups]
        user_dict['role'] = self.role
        return user_dict

    @property
    def role(self):
        return self.roles[0].name

    def is_sys_admin(self):
        return self.role == SYSTEM_ADMIN_ROLE

    def is_tenant_admin(self):
        return self.role == TENANT_ADMIN_ROLE

    def is_default_user(self):
        return self.role == DEFAULT_ROLE

    def is_viewer(self):
        return self.role == VIEWER_ROLE

    def is_admin(self):
        return self.role in ADMINISTRATOR_ROLES

    def is_suspended(self):
        return self.role == SUSPENDED_ROLE


class Role(SQLModelBase, RoleMixin):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, nullable=False, index=True)

    description = db.Column(db.Text)

    def _get_unique_id(self):
        return 'name', self.name

#  endregion


#  region Resources
class Blueprint(SQLResource):
    __tablename__ = 'blueprints'

    storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    main_file_name = db.Column(db.Text, nullable=False)
    plan = db.Column(db.PickleType, nullable=False)
    updated_at = db.Column(UTCDateTime)
    description = db.Column(db.Text)

    tenant_id = foreign_key(Tenant, id_col_name='id')
    tenant = one_to_many_relationship(
        child_class_name='Blueprint',
        column_name='tenant_id',
        parent_class_name='Tenant',
        back_reference_name='blueprints',
        parent_id_name='id'
    )


class Snapshot(SQLResource):
    __tablename__ = 'snapshots'

    storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    status = db.Column(db.Enum(*SnapshotState.STATES, name='snapshot_status'))
    error = db.Column(db.Text)

    tenant_id = foreign_key(Tenant, id_col_name='id')
    tenant = one_to_many_relationship(
        child_class_name='Snapshot',
        column_name='tenant_id',
        parent_class_name='Tenant',
        back_reference_name='snapshots',
        parent_id_name='id'
    )


class Deployment(SQLResource):
    __tablename__ = 'deployments'

    # See base class for an explanation on these properties
    join_properties = {
        'blueprint_id': {
            # No need to provide the Blueprint table, as it's already joined
            'models': [Blueprint],
            'column': Blueprint.id.label('blueprint_id')
        },
        'tenant_id': {
            'models': [Blueprint],
            'column': Tenant.id.label('tenant_id')
        }
    }
    join_order = 2

    _private_fields = SQLResource._private_fields + ['blueprint_storage_id']

    storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    description = db.Column(db.Text)
    inputs = db.Column(db.PickleType)
    groups = db.Column(db.PickleType)
    permalink = db.Column(db.Text)
    policy_triggers = db.Column(db.PickleType)
    policy_types = db.Column(db.PickleType)
    outputs = db.Column(db.PickleType(comparator=lambda *a: False))
    scaling_groups = db.Column(db.PickleType)
    updated_at = db.Column(UTCDateTime)
    workflows = db.Column(db.PickleType(comparator=lambda *a: False))

    blueprint_storage_id = foreign_key(Blueprint)
    blueprint = one_to_many_relationship(
        child_class_name='Deployment',
        column_name='blueprint_storage_id',
        parent_class_name='Blueprint',
        back_reference_name='deployments'
    )

    @property
    def tenant(self):
        return self.blueprint.tenant

    @property
    def blueprint_id(self):
        return self.blueprint.id


class Execution(SQLResource):
    __tablename__ = 'executions'

    # See base class for an explanation on these properties
    join_properties = {
        'blueprint_id': {
            'models': [Deployment, Blueprint],
            'column': Blueprint.id.label('blueprint_id')
        },
        'deployment_id': {
            'models': [Deployment],
            'column': Deployment.id.label('deployment_id')
        }
    }
    join_order = 3

    _private_fields = SQLResource._private_fields + ['deployment_storage_id']

    storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    error = db.Column(db.Text)
    is_system_workflow = db.Column(db.Boolean, nullable=False)
    parameters = db.Column(db.PickleType)
    status = db.Column(
        db.Enum(*ExecutionState.STATES, name='execution_status')
    )
    workflow_id = db.Column(db.Text, nullable=False)

    deployment_storage_id = foreign_key(Deployment, nullable=True)
    deployment = one_to_many_relationship(
        child_class_name='Execution',
        column_name='deployment_storage_id',
        parent_class_name='Deployment',
        back_reference_name='executions'
    )

    # Executions of system workflow don't have a deployment attached,
    # hence the need for an explicit tenant field
    tenant_id = foreign_key(Tenant, id_col_name='id')
    tenant = one_to_many_relationship(
        child_class_name='Execution',
        column_name='tenant_id',
        parent_class_name='Tenant',
        back_reference_name='executions',
        parent_id_name='id'
    )

    @property
    def deployment_id(self):
        return self.deployment.id if self.deployment else None

    @property
    def blueprint_id(self):
        return self.deployment.blueprint_id if self.deployment else None

    def __str__(self):
        id_name, id_value = self._get_unique_id()
        return '<{0} {1}=`{2}` (status={3})>'.format(
            self.__class__.__name__,
            id_name,
            id_value,
            self.status
        )


class DeploymentUpdate(SQLResource):
    __tablename__ = 'deployment_updates'

    # See base class for an explanation on these properties
    join_properties = {
        'execution_id': {
            'models': [Execution],
            'column': Execution.id.label('execution_id')
        },
        'deployment_id': {
            'models': [Deployment],
            'column': Deployment.id.label('deployment_id')
        },
        'tenant_id': {
            'models': [Deployment, Blueprint],
            'column': Tenant.id.label('tenant_id')
        }
    }
    join_order = 4

    _private_fields = SQLResource._private_fields + ['execution_storage_id']

    storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    deployment_plan = db.Column(db.PickleType)
    deployment_update_node_instances = db.Column(db.PickleType)
    deployment_update_deployment = db.Column(db.PickleType)
    deployment_update_nodes = db.Column(db.PickleType)
    modified_entity_ids = db.Column(db.PickleType)
    state = db.Column(db.Text)

    execution_storage_id = foreign_key(Execution, nullable=True)
    execution = one_to_many_relationship(
        child_class_name='DeploymentUpdate',
        column_name='execution_storage_id',
        parent_class_name='Execution',
        back_reference_name='deployment_updates'
    )

    deployment_storage_id = foreign_key(Deployment)
    deployment = one_to_many_relationship(
        child_class_name='DeploymentUpdate',
        column_name='deployment_storage_id',
        parent_class_name='Deployment',
        back_reference_name='deployment_updates'
    )

    @property
    def tenant(self):
        return self.deployment.tenant

    @property
    def execution_id(self):
        return self.execution.id if self.execution else None

    @property
    def deployment_id(self):
        return self.deployment.id

    def to_dict(self, suppress_error=False):
        dep_update_dict = super(DeploymentUpdate, self).to_dict(suppress_error)
        # Taking care of the fact the DeploymentSteps are objects
        dep_update_dict['steps'] = [step.to_dict() for step in self.steps]
        return dep_update_dict


class DeploymentUpdateStep(SQLResource):
    __tablename__ = 'deployment_update_steps'

    # See base class for an explanation on these properties
    join_properties = {
        'deployment_update_id': {
            'models': [DeploymentUpdate],
            'column': DeploymentUpdate.id.label('deployment_update_id')
        },
        'tenant_id': {
            'models': [DeploymentUpdate, Deployment, Blueprint],
            'column': Tenant.id.label('tenant_id')
        }
    }
    join_order = 5

    _private_fields = \
        SQLResource._private_fields + ['deployment_update_storage_id']

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    action = db.Column(db.Enum(*ACTION_TYPES, name='action_type'))
    entity_id = db.Column(db.Text, nullable=False)
    entity_type = db.Column(db.Enum(*ENTITY_TYPES, name='entity_type'))

    deployment_update_storage_id = foreign_key(DeploymentUpdate)
    deployment_update = one_to_many_relationship(
        child_class_name='DeploymentUpdateStep',
        column_name='deployment_update_storage_id',
        parent_class_name='DeploymentUpdate',
        back_reference_name='steps'
    )

    @property
    def tenant(self):
        return self.deployment_update.tenant

    @property
    def deployment_update_id(self):
        return self.deployment_update.id


class DeploymentModification(SQLResource):
    __tablename__ = 'deployment_modifications'

    # See base class for an explanation on these properties
    join_properties = {
        'deployment_id': {
            'models': [Deployment],
            'column': Deployment.id.label('deployment_id')
        },
        'tenant_id': {
            'models': [Deployment, Blueprint],
            'column': Tenant.id.label('tenant_id')
        }
    }
    join_order = 3

    _private_fields = SQLResource._private_fields + ['deployment_storage_id']

    storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)

    context = db.Column(db.PickleType)
    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    ended_at = db.Column(UTCDateTime, index=True)
    modified_nodes = db.Column(db.PickleType)
    node_instances = db.Column(db.PickleType)
    status = db.Column(db.Enum(
        *DeploymentModificationState.STATES,
        name='deployment_modification_status'
    ))

    deployment_storage_id = foreign_key(Deployment)
    deployment = one_to_many_relationship(
        child_class_name='DeploymentModification',
        column_name='deployment_storage_id',
        parent_class_name='Deployment',
        back_reference_name='modifications'
    )

    @property
    def tenant(self):
        return self.deployment.tenant

    @property
    def deployment_id(self):
        return self.deployment.id


class Node(SQLResource):
    __tablename__ = 'nodes'

    # See base class for an explanation on these properties
    is_id_unique = False
    join_properties = {
        'blueprint_id': {
            'models': [Deployment, Blueprint],
            'column': Blueprint.id.label('blueprint_id')
        },
        'deployment_id': {
            'models': [Deployment],
            'column': Deployment.id.label('deployment_id')
        },
        'tenant_id': {
            'models': [Deployment, Blueprint],
            'column': Tenant.id.label('tenant_id')
        }
    }
    join_order = 3

    _private_fields = SQLResource._private_fields + ['deployment_storage_id']

    storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)

    deploy_number_of_instances = db.Column(db.Integer, nullable=False)
    # TODO: This probably should be a foreign key, but there's no guarantee
    # in the code, currently, that the host will be created beforehand
    host_id = db.Column(db.Text)
    max_number_of_instances = db.Column(db.Integer, nullable=False)
    min_number_of_instances = db.Column(db.Integer, nullable=False)
    number_of_instances = db.Column(db.Integer, nullable=False)
    planned_number_of_instances = db.Column(db.Integer, nullable=False)
    plugins = db.Column(db.PickleType)
    plugins_to_install = db.Column(db.PickleType)
    properties = db.Column(db.PickleType)
    relationships = db.Column(db.PickleType)
    operations = db.Column(db.PickleType)
    type = db.Column(db.Text, nullable=False, index=True)
    type_hierarchy = db.Column(db.PickleType)

    deployment_storage_id = foreign_key(Deployment)
    deployment = one_to_many_relationship(
        child_class_name='Node',
        column_name='deployment_storage_id',
        parent_class_name='Deployment',
        back_reference_name='nodes'
    )

    @property
    def tenant(self):
        return self.deployment.tenant

    @property
    def deployment_id(self):
        return self.deployment.id

    @property
    def blueprint_id(self):
        return self.deployment.blueprint_id


class NodeInstance(SQLResource):
    __tablename__ = 'node_instances'

    # See base class for an explanation on these properties
    join_properties = {
        'node_id': {
            'models': [Node],
            'column': Node.id.label('node_id')
        },
        'deployment_id': {
            'models': [Node, Deployment],
            'column': Deployment.id.label('deployment_id')
        },
        'tenant_id': {
            'models': [Node, Deployment, Blueprint],
            'column': Tenant.id.label('tenant_id')
        }
    }
    join_order = 4

    _private_fields = SQLResource._private_fields + ['node_storage_id']

    storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)

    # TODO: This probably should be a foreign key, but there's no guarantee
    # in the code, currently, that the host will be created beforehand
    host_id = db.Column(db.Text)
    relationships = db.Column(db.PickleType)
    runtime_properties = db.Column(db.PickleType)
    scaling_groups = db.Column(db.PickleType)
    state = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, default=1)

    node_storage_id = foreign_key(Node)
    node = one_to_many_relationship(
        child_class_name='NodeInstance',
        column_name='node_storage_id',
        parent_class_name='Node',
        back_reference_name='node_instances'
    )

    @property
    def tenant(self):
        return self.deployment.tenant

    @property
    def node_id(self):
        return self.node.id

    @property
    def deployment_id(self):
        return self.node.deployment_id


class ProviderContext(SQLResource):
    __tablename__ = 'provider_context'

    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    context = db.Column(db.PickleType, nullable=False)


class Plugin(SQLResource):
    __tablename__ = 'plugins'

    storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)

    archive_name = db.Column(db.Text, nullable=False, index=True)
    distribution = db.Column(db.Text)
    distribution_release = db.Column(db.Text)
    distribution_version = db.Column(db.Text)
    excluded_wheels = db.Column(db.PickleType)
    package_name = db.Column(db.Text, nullable=False, index=True)
    package_source = db.Column(db.Text)
    package_version = db.Column(db.Text)
    supported_platform = db.Column(db.PickleType)
    supported_py_versions = db.Column(db.PickleType)
    uploaded_at = db.Column(UTCDateTime, nullable=False, index=True)
    wheels = db.Column(db.PickleType, nullable=False)

    tenant_id = foreign_key(Tenant, id_col_name='id')
    tenant = one_to_many_relationship(
        child_class_name='Plugin',
        column_name='tenant_id',
        parent_class_name='Tenant',
        back_reference_name='plugins',
        parent_id_name='id'
    )

# endregion

user_datastore = SQLAlchemyUserDatastore(db, User, Role)

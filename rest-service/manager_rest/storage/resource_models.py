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

from flask_restful import fields as flask_fields
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.associationproxy import association_proxy

from manager_rest.utils import classproperty
from manager_rest.rest.responses import Workflow
from manager_rest.deployment_update.constants import ACTION_TYPES, ENTITY_TYPES

from .models_base import db, UTCDateTime
from .relationships import foreign_key, one_to_many_relationship
from .resource_models_base import TopLevelResource, DerivedResource
from .mixins import (
    DerivedMixin,
    DerivedTenantMixin,
    TopLevelCreatorMixin,
    TopLevelMixin,
)
from .models_states import (DeploymentModificationState,
                            SnapshotState,
                            ExecutionState)


# region Top Level Resources

class Blueprint(TopLevelResource):
    __tablename__ = 'blueprints'

    skipped_fields = dict(
        TopLevelResource.skipped_fields,
        v1=['main_file_name', 'description']
    )

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    main_file_name = db.Column(db.Text, nullable=False)
    plan = db.Column(db.PickleType, nullable=False)
    updated_at = db.Column(UTCDateTime)
    description = db.Column(db.Text)


class Snapshot(TopLevelResource):
    __tablename__ = 'snapshots'

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    status = db.Column(db.Enum(*SnapshotState.STATES, name='snapshot_status'))
    error = db.Column(db.Text)


class Plugin(TopLevelResource):
    __tablename__ = 'plugins'

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

# endregion


# region Derived Resources

class Deployment(TopLevelCreatorMixin, DerivedResource, DerivedTenantMixin):
    __tablename__ = 'deployments'

    skipped_fields = dict(
        TopLevelResource.skipped_fields,
        v1=['scaling_groups'],
        v2=['scaling_groups']
    )
    proxies = {'blueprint_id': flask_fields.String}
    _private_fields = DerivedResource._private_fields + ['blueprint_fk']

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

    blueprint_fk = foreign_key(Blueprint.storage_id)

    @declared_attr
    def blueprint(cls):
        return one_to_many_relationship(cls, Blueprint, cls.blueprint_fk)

    @hybrid_property
    def parent(self):
        return self.blueprint

    @parent.expression
    def parent(cls):
        return Blueprint

    blueprint_id = association_proxy('blueprint', 'id')
    tenant_id = association_proxy('blueprint', 'tenant_id')

    @classproperty
    def resource_fields(self):
        fields = super(Deployment, self).resource_fields
        fields['workflows'] = flask_fields.List(
            flask_fields.Nested(Workflow.resource_fields)
        )
        return fields

    def to_response(self):
        dep_dict = super(Deployment, self).to_response()
        dep_dict['workflows'] = self._list_workflows(self.workflows)
        return dep_dict

    @staticmethod
    def _list_workflows(deployment_workflows):
        if deployment_workflows is None:
            return None

        return [Workflow(name=wf_name,
                         created_at=None,
                         parameters=wf.get('parameters', dict()))
                for wf_name, wf in deployment_workflows.iteritems()]


class Execution(TopLevelMixin, DerivedResource):
    __tablename__ = 'executions'

    proxies = {
        'blueprint_id': flask_fields.String,
        'deployment_id': flask_fields.String
    }
    _private_fields = DerivedResource._private_fields + ['deployment_fk']

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    error = db.Column(db.Text)
    is_system_workflow = db.Column(db.Boolean, nullable=False)
    parameters = db.Column(db.PickleType)
    status = db.Column(
        db.Enum(*ExecutionState.STATES, name='execution_status')
    )
    workflow_id = db.Column(db.Text, nullable=False)

    deployment_fk = foreign_key(Deployment.storage_id, nullable=True)

    @declared_attr
    def deployment(cls):
        return one_to_many_relationship(cls, Deployment, cls.deployment_fk)

    deployment_id = association_proxy('deployment', 'id')
    blueprint_id = association_proxy('deployment', 'blueprint_id')

    @hybrid_property
    def parent(self):
        return self.deployment

    @parent.expression
    def parent(cls):
        return Deployment

    def __str__(self):
        id_name, id_value = self._get_identifier()
        return '<{0} {1}=`{2}` (status={3})>'.format(
            self.__class__.__name__,
            id_name,
            id_value,
            self.status
        )


class Event(DerivedResource, DerivedMixin):

    """Execution events."""

    __tablename__ = 'events'

    proxies = {
        'execution_id': flask_fields.String
    }

    timestamp = db.Column(UTCDateTime, nullable=False, index=True)
    execution_fk = foreign_key(Execution.storage_id, nullable=False)
    message = db.Column(db.Text)
    message_code = db.Column(db.Text)

    event_type = db.Column(db.Text)

    @declared_attr
    def execution(cls):
        return one_to_many_relationship(cls, Execution, cls.execution_fk)

    execution_id = association_proxy('execution', 'id')

    @hybrid_property
    def parent(self):
        return self.execution

    @parent.expression
    def parent(cls):
        return Execution


class Log(DerivedResource, DerivedMixin):

    """Execution logs."""

    __tablename__ = 'logs'

    proxies = {
        'execution_id': flask_fields.String
    }

    timestamp = db.Column(UTCDateTime, nullable=False, index=True)
    execution_fk = foreign_key(Execution.storage_id, nullable=False)
    message = db.Column(db.Text)
    message_code = db.Column(db.Text)

    logger = db.Column(db.Text)
    level = db.Column(db.Text)

    @declared_attr
    def execution(cls):
        return one_to_many_relationship(cls, Execution, cls.execution_fk)

    execution_id = association_proxy('execution', 'id')

    @hybrid_property
    def parent(self):
        return self.execution

    @parent.expression
    def parent(cls):
        return Execution


class DeploymentUpdate(DerivedResource, DerivedMixin):
    __tablename__ = 'deployment_updates'

    proxies = {
        'execution_id': flask_fields.String,
        'deployment_id': flask_fields.String,
        'steps': flask_fields.Raw,
    }
    _private_fields = DerivedResource._private_fields + ['execution_fk']

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    deployment_plan = db.Column(db.PickleType)
    deployment_update_node_instances = db.Column(db.PickleType)
    deployment_update_deployment = db.Column(db.PickleType)
    deployment_update_nodes = db.Column(db.PickleType)
    modified_entity_ids = db.Column(db.PickleType)
    state = db.Column(db.Text)

    execution_fk = foreign_key(Execution.storage_id, nullable=True)

    @declared_attr
    def execution(cls):
        return one_to_many_relationship(cls, Execution, cls.execution_fk)

    deployment_fk = foreign_key(Deployment.storage_id)

    @declared_attr
    def deployment(cls):
        return one_to_many_relationship(cls, Deployment, cls.deployment_fk)

    @hybrid_property
    def parent(self):
        return self.deployment

    @parent.expression
    def parent(cls):
        return Deployment

    deployment_id = association_proxy('deployment', 'id')
    execution_id = association_proxy('execution', 'id')
    tenant_id = association_proxy('deployment', 'tenant_id')

    def to_response(self):
        dep_update_dict = super(DeploymentUpdate, self).to_response()
        # Taking care of the fact the DeploymentSteps are objects
        dep_update_dict['steps'] = [step.to_dict() for step in self.steps]
        return dep_update_dict


class DeploymentUpdateStep(DerivedResource, DerivedMixin):
    __tablename__ = 'deployment_update_steps'

    proxies = {'deployment_update_id': flask_fields.String}
    _private_fields = \
        DerivedResource._private_fields + ['deployment_update_fk']

    action = db.Column(db.Enum(*ACTION_TYPES, name='action_type'))
    entity_id = db.Column(db.Text, nullable=False)
    entity_type = db.Column(db.Enum(*ENTITY_TYPES, name='entity_type'))

    deployment_update_fk = foreign_key(DeploymentUpdate.storage_id)

    @declared_attr
    def deployment_update(cls):
        return one_to_many_relationship(cls,
                                        DeploymentUpdate,
                                        cls.deployment_update_fk,
                                        backreference='steps')

    @hybrid_property
    def parent(self):
        return self.deployment_update

    @parent.expression
    def parent(cls):
        return DeploymentUpdate

    deployment_update_id = association_proxy('deployment_update', 'id')
    tenant_id = association_proxy('deployment_update', 'tenant_id')


class DeploymentModification(DerivedResource, DerivedMixin):
    __tablename__ = 'deployment_modifications'

    proxies = {'deployment_id': flask_fields.String}
    _private_fields = DerivedResource._private_fields + ['deployment_fk']

    context = db.Column(db.PickleType)
    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    ended_at = db.Column(UTCDateTime, index=True)
    modified_nodes = db.Column(db.PickleType)
    node_instances = db.Column(db.PickleType)
    status = db.Column(db.Enum(
        *DeploymentModificationState.STATES,
        name='deployment_modification_status'
    ))

    deployment_fk = foreign_key(Deployment.storage_id)

    @declared_attr
    def deployment(cls):
        return one_to_many_relationship(cls,
                                        Deployment,
                                        cls.deployment_fk,
                                        backreference='modifications')

    @hybrid_property
    def parent(self):
        return self.deployment

    @parent.expression
    def parent(cls):
        return Deployment

    deployment_id = association_proxy('deployment', 'id')
    tenant_id = association_proxy('deployment', 'tenant_id')


class Node(DerivedResource, DerivedMixin):
    __tablename__ = 'nodes'

    is_id_unique = False
    skipped_fields = dict(
        TopLevelResource.skipped_fields,
        v1=['max_number_of_instances', 'min_number_of_instances'],
        v2=['max_number_of_instances', 'min_number_of_instances']
    )
    proxies = {
        'blueprint_id': flask_fields.String,
        'deployment_id': flask_fields.String
    }
    _private_fields = DerivedResource._private_fields + ['deployment_fk']

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

    deployment_fk = foreign_key(Deployment.storage_id)

    @declared_attr
    def deployment(cls):
        return one_to_many_relationship(cls, Deployment, cls.deployment_fk)

    @hybrid_property
    def parent(self):
        return self.deployment

    @parent.expression
    def parent(cls):
        return Deployment

    deployment_id = association_proxy('deployment', 'id')
    blueprint_id = association_proxy('deployment', 'blueprint_id')
    tenant_id = association_proxy('deployment', 'tenant_id')


class NodeInstance(DerivedResource, DerivedMixin):
    __tablename__ = 'node_instances'

    skipped_fields = dict(
        TopLevelResource.skipped_fields,
        v1=['scaling_groups'],
        v2=['scaling_groups']
    )
    proxies = {
        'node_id': flask_fields.String,
        'deployment_id': flask_fields.String
    }
    _private_fields = DerivedResource._private_fields + ['node_fk']

    # TODO: This probably should be a foreign key, but there's no guarantee
    # in the code, currently, that the host will be created beforehand
    host_id = db.Column(db.Text)
    relationships = db.Column(db.PickleType)
    runtime_properties = db.Column(db.PickleType)
    scaling_groups = db.Column(db.PickleType)
    state = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, default=1)

    node_fk = foreign_key(Node.storage_id)

    @declared_attr
    def node(cls):
        return one_to_many_relationship(cls, Node, cls.node_fk)

    @hybrid_property
    def parent(self):
        return self.node

    @parent.expression
    def parent(cls):
        return Node

    node_id = association_proxy('node', 'id')
    deployment_id = association_proxy('node', 'deployment_id')
    tenant_id = association_proxy('node', 'tenant_id')

# endregion

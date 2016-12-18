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
from .relationships import foreign_key
from .resource_models_base import TopLevelResource, DerivedResource
from .mixins import (
    DerivedMixin,
    DerivedTenantMixin,
    TopLevelCreatorMixin,
    TopLevelMixin,
)


from aria.storage import (
    base_model as base,
    type as aria_types
)

# region Top Level Resources


class Blueprint(TopLevelResource, base.BlueprintBase):
    __tablename__ = 'blueprints'

    skipped_fields = dict(
        TopLevelResource.skipped_fields,
        v1=['main_file_name', 'description']
    )

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    updated_at = db.Column(UTCDateTime, index=True)


class Snapshot(TopLevelResource):
    __tablename__ = 'snapshots'

    CREATED = 'created'
    FAILED = 'failed'
    CREATING = 'creating'
    UPLOADED = 'uploaded'

    STATES = [CREATED, FAILED, CREATING, UPLOADED]
    END_STATES = [CREATED, FAILED, UPLOADED]

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    status = db.Column(db.Enum(*STATES, name='snapshot_status'))
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

class Deployment(TopLevelCreatorMixin, DerivedResource, DerivedTenantMixin, base.DeploymentBase):
    __tablename__ = 'deployments'

    skipped_fields = dict(
        TopLevelResource.skipped_fields,
        v1=['scaling_groups'],
        v2=['scaling_groups']
    )
    proxies = {'blueprint_id': flask_fields.String}
    _private_fields = DerivedResource._private_fields + base.DeploymentBase._private_fields

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    updated_at = db.Column(UTCDateTime)

    @hybrid_property
    def parent(self):
        return self.blueprint

    @parent.expression
    def parent(cls):
        return Blueprint

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


class Execution(TopLevelMixin, DerivedResource, base.ExecutionBase):
    __tablename__ = 'executions'

    proxies = {
        'blueprint_id': flask_fields.String,
        'deployment_id': flask_fields.String
    }
    _private_fields = DerivedResource._private_fields + base.ExecutionBase._private_fields

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    started_at = db.Column(UTCDateTime, nullable=True, index=True)
    ended_at = db.Column(UTCDateTime, nullable=True, index=True)
    workflow_id = db.Column(db.Text)

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
    message = db.Column(db.Text)
    message_code = db.Column(db.Text)

    event_type = db.Column(db.Text)

    execution_id = foreign_key(Execution.storage_id, nullable=False)

    @declared_attr
    def execution(cls):
        return cls.one_to_many_relationship('execution_id', 'Execution')

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
    message = db.Column(db.Text)
    message_code = db.Column(db.Text)

    logger = db.Column(db.Text)
    level = db.Column(db.Text)

    execution_id = foreign_key(Execution.storage_id, nullable=False)

    @declared_attr
    def execution(cls):
        return cls.one_to_many_relationship('execution_id', 'Execution')

    @hybrid_property
    def parent(self):
        return self.execution

    @parent.expression
    def parent(cls):
        return Execution


class DeploymentUpdate(DerivedResource, DerivedMixin, base.DeploymentUpdateBase):
    __tablename__ = 'deployment_updates'

    proxies = {
        'execution_id': flask_fields.String,
        'deployment_id': flask_fields.String,
        'steps': flask_fields.Raw,
    }
    _private_fields = DerivedResource._private_fields + base.DeploymentUpdateBase._private_fields

    created_at = db.Column(UTCDateTime, nullable=False, index=True)

    @hybrid_property
    def parent(self):
        return self.deployment

    @parent.expression
    def parent(cls):
        return Deployment

    tenant_id = association_proxy('deployment', 'tenant_id')

    def to_response(self):
        dep_update_dict = super(DeploymentUpdate, self).to_response()
        # Taking care of the fact the DeploymentSteps are objects
        dep_update_dict['steps'] = [step.to_dict() for step in self.steps]
        return dep_update_dict


class DeploymentUpdateStep(DerivedResource, DerivedMixin, base.DeploymentUpdateStepBase):
    __tablename__ = 'deployment_update_steps'

    proxies = {'deployment_update_id': flask_fields.String}
    _private_fields = \
        DerivedResource._private_fields + base.DeploymentUpdateStepBase._private_fields

    @hybrid_property
    def parent(self):
        return self.deployment_update

    @parent.expression
    def parent(cls):
        return DeploymentUpdate

    tenant_id = association_proxy('deployment_update', 'tenant_id')


class DeploymentModification(DerivedResource, DerivedMixin, base.DeploymentModificationBase):
    __tablename__ = 'deployment_modifications'

    proxies = {'deployment_id': flask_fields.String}
    _private_fields = \
        DerivedResource._private_fields + base.DeploymentModificationBase._private_fields

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    ended_at = db.Column(UTCDateTime, index=True)

    @hybrid_property
    def parent(self):
        return self.deployment

    @parent.expression
    def parent(cls):
        return Deployment

    tenant_id = association_proxy('deployment', 'tenant_id')


class Node(DerivedResource, DerivedMixin, base.NodeBase):
    __tablename__ = 'nodes'

    is_id_unique = False
    skipped_fields = dict(
        TopLevelResource.skipped_fields,
        v1=['max_number_of_instances', 'min_number_of_instances'],
        v2=['max_number_of_instances', 'min_number_of_instances']
    )
    proxies = {
        'blueprint_id': flask_fields.String,
        'deployment_id': flask_fields.String,
        'host_id': flask_fields.String,
    }
    _private_fields = DerivedResource._private_fields + base.NodeBase._private_fields

    @hybrid_property
    def parent(self):
        return self.deployment

    @parent.expression
    def parent(cls):
        return Deployment

    tenant_id = association_proxy('deployment', 'tenant_id')
    relationships = db.Column(aria_types.List)


class NodeInstance(DerivedResource, DerivedMixin, base.NodeInstanceBase):
    __tablename__ = 'node_instances'

    skipped_fields = dict(
        TopLevelResource.skipped_fields,
        v1=['scaling_groups'],
        v2=['scaling_groups']
    )
    proxies = {
        'node_id': flask_fields.String,
        'deployment_id': flask_fields.String,
        'host_id': flask_fields.String,
    }
    _private_fields = DerivedResource._private_fields + base.NodeInstanceBase._private_fields

    @hybrid_property
    def parent(self):
        return self.node

    @parent.expression
    def parent(cls):
        return Node

    tenant_id = association_proxy('node', 'tenant_id')

    relationships = db.Column(aria_types.List)


class Task(DerivedResource, DerivedMixin, base.TaskBase):

    __tablename__ = 'tasks'

    proxies = {'deployment_id': flask_fields.String}
    _private_fields = DerivedResource._private_fields + base.TaskBase._private_fields

    @hybrid_property
    def parent(self):
        return self.execution

    @parent.expression
    def parent(cls):
        return Execution

    relationship_instance_fk = None
    relationship_instance_id = None
    relationship_instance = None

# endregion

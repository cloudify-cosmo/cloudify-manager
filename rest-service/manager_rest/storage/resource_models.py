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

from .models_base import db, UTCDateTime
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


class Blueprint(base.BlueprintBase, TopLevelResource):
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


class Plugin(base.PluginBase, TopLevelResource):
    uploaded_at = db.Column(UTCDateTime, nullable=False, index=True)
    excluded_wheels = db.Column(aria_types.List)
# endregion


# region Derived Resources

class Deployment(base.DeploymentBase,
                 TopLevelCreatorMixin,
                 DerivedResource,
                 DerivedTenantMixin):

    skipped_fields = dict(
        TopLevelResource.skipped_fields,
        v1=['scaling_groups'],
        v2=['scaling_groups']
    )
    proxies = {'blueprint_id': flask_fields.String}
    _private_fields = DerivedResource._private_fields + \
        base.DeploymentBase._private_fields

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    updated_at = db.Column(UTCDateTime)

    @hybrid_property
    def parent(self):
        return self.blueprint

    @parent.expression
    def parent(cls):
        return Blueprint

    tenant_id = association_proxy('blueprint', 'tenant_id')
    blueprint_id = association_proxy('blueprint',
                                     Blueprint.name_column_name())

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

    @staticmethod
    def _dict_workflows(workflows_list):
        return {workflow.name: workflow.parameters
                for workflow in workflows_list}

    def __init__(self, *args, **kwargs):
        kwargs['workflows'] = self._dict_workflows(kwargs.pop('workflows', {}))
        super(Deployment, self).__init__(*args, **kwargs)


class Execution(base.ExecutionBase, TopLevelMixin, DerivedResource):

    proxies = {
        'deployment_id': flask_fields.String,
        'blueprint_id': flask_fields.String
    }
    _private_fields = DerivedResource._private_fields + \
        base.ExecutionBase._private_fields

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

    def __repr__(self):
        id_name = self.name_column_name()
        return '<{0} {1}=`{2}` (status={3})>'.format(
            self.__class__.__name__,
            id_name,
            getattr(self, id_name),
            self.status
        )

    # old style id support
    blueprint_id = association_proxy(
        'deployment',
        'blueprint_{0}'.format(Blueprint.name_column_name()))

    deployment_id = association_proxy(
        'deployment', Deployment.name_column_name())


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

    @declared_attr
    def execution_fk(cls):
        return cls.foreign_key(Execution, nullable=False)

    @declared_attr
    def execution(cls):
        return cls.one_to_many_relationship('execution_fk')

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

    @declared_attr
    def execution_fk(cls):
        return cls.foreign_key(Execution, nullable=False)

    @declared_attr
    def execution(cls):
        return cls.one_to_many_relationship('execution_fk')

    @hybrid_property
    def parent(self):
        return self.execution

    @parent.expression
    def parent(cls):
        return Execution


class DeploymentUpdate(base.DeploymentUpdateBase,
                       DerivedResource,
                       DerivedMixin):

    proxies = {
        'execution_id': flask_fields.String,
        'deployment_id': flask_fields.String,
        'steps': flask_fields.Raw,
    }
    _private_fields = DerivedResource._private_fields + \
        base.DeploymentUpdateBase._private_fields

    created_at = db.Column(UTCDateTime, nullable=False, index=True)

    @hybrid_property
    def parent(self):
        return self.deployment

    @parent.expression
    def parent(cls):
        return Deployment

    tenant_id = association_proxy('deployment', 'tenant_id')

    # old style id support
    execution_id = association_proxy('execution',
                                     Execution.name_column_name())
    deployment_id = association_proxy('deployment',
                                      Deployment.name_column_name())

    def to_response(self):
        dep_update_dict = super(DeploymentUpdate, self).to_response()
        # Taking care of the fact the DeploymentSteps are objects
        dep_update_dict['steps'] = [step.to_dict() for step in self.steps]
        return dep_update_dict


class DeploymentUpdateStep(base.DeploymentUpdateStepBase,
                           DerivedResource,
                           DerivedMixin):

    proxies = {'deployment_update_id': flask_fields.String}
    _private_fields = DerivedResource._private_fields + \
        base.DeploymentUpdateStepBase._private_fields

    @hybrid_property
    def parent(self):
        return self.deployment_update

    @parent.expression
    def parent(cls):
        return DeploymentUpdate

    tenant_id = association_proxy('deployment_update', 'tenant_id')

    # old style id support
    deployment_update_id = association_proxy(
        'deployment_update', DeploymentUpdate.name_column_name())


class DeploymentModification(base.DeploymentModificationBase,
                             DerivedResource,
                             DerivedMixin):

    proxies = {'deployment_id': flask_fields.String}
    _private_fields = DerivedResource._private_fields + \
        base.DeploymentModificationBase._private_fields

    created_at = db.Column(UTCDateTime, nullable=False, index=True)
    ended_at = db.Column(UTCDateTime, index=True)

    @hybrid_property
    def parent(self):
        return self.deployment

    @parent.expression
    def parent(cls):
        return Deployment

    tenant_id = association_proxy('deployment', 'tenant_id')

    # old style id support
    deployment_id = association_proxy('deployment',
                                      Deployment.name_column_name())


class Node(base.NodeBase, DerivedResource, DerivedMixin):

    is_id_unique = False
    skipped_fields = dict(
        TopLevelResource.skipped_fields,
        v1=['max_number_of_instances', 'min_number_of_instances'],
        v2=['max_number_of_instances', 'min_number_of_instances']
    )
    proxies = {
        'deployment_id': flask_fields.String,
        'blueprint_id': flask_fields.String,
        'host_id': flask_fields.String,
    }
    _private_fields = \
        DerivedResource._private_fields + base.NodeBase._private_fields

    @hybrid_property
    def parent(self):
        return self.deployment

    @parent.expression
    def parent(cls):
        return Deployment

    tenant_id = association_proxy('deployment', 'tenant_id')
    relationships = db.Column(aria_types.List)
    plugins_to_install = db.Column(aria_types.List)

    # old style id support
    @declared_attr
    def host_id(cls):
        return association_proxy('host', cls.name_column_name())

    deployment_id = association_proxy('deployment',
                                      Deployment.name_column_name())

    blueprint_id = association_proxy(
        'deployment',
        'blueprint_{0}'.format(Blueprint.name_column_name()))


class NodeInstance(base.NodeInstanceBase, DerivedResource, DerivedMixin):

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
    _private_fields = DerivedResource._private_fields + \
        base.NodeInstanceBase._private_fields

    @hybrid_property
    def parent(self):
        return self.node

    @parent.expression
    def parent(cls):
        return Node

    tenant_id = association_proxy('node', 'tenant_id')

    # old style id support
    node_id = association_proxy('node', Node.name_column_name())
    deployment_id = association_proxy('node', 'deployment_id')

    @declared_attr
    def host_id(cls):
        return association_proxy('host', cls.name_column_name())

    relationships = db.Column(aria_types.List)


class Task(base.TaskBase, DerivedResource, DerivedMixin):
    """
    This model is not yet used by cloudify but will be by the ARIA
    workflow engine
    """
    proxies = {'deployment_id': flask_fields.String}
    _private_fields = \
        DerivedResource._private_fields + base.TaskBase._private_fields

    @hybrid_property
    def parent(self):
        return self.execution

    @parent.expression
    def parent(cls):
        return Execution

    # old style id support
    execution_id = association_proxy('execution',
                                     Execution.name_column_name())

    relationship_instance_fk = None
    relationship_instance_name = None
    relationship_instance = None

# endregion

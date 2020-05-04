########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.


from os import path
from datetime import datetime

from flask_restful import fields as flask_fields

from sqlalchemy import case, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import func, select, table, column
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.associationproxy import association_proxy

from cloudify.models_states import (AgentState,
                                    SnapshotState,
                                    ExecutionState,
                                    DeploymentModificationState)

from manager_rest import config
from manager_rest.rest.responses import Workflow
from manager_rest.utils import classproperty, files_in_folder
from manager_rest.deployment_update.constants import ACTION_TYPES, ENTITY_TYPES
from manager_rest.constants import (FILE_SERVER_PLUGINS_FOLDER,
                                    FILE_SERVER_RESOURCES_FOLDER)

from .models_base import (
    db,
    JSONString,
    UTCDateTime,
)
from .resource_models_base import SQLResourceBase
from .relationships import foreign_key, one_to_many_relationship


class CreatedAtMixin(object):
    created_at = db.Column(UTCDateTime, nullable=False, index=True)

    @classmethod
    def default_sort_column(cls):
        """Models that have created_at, sort on it by default."""
        return cls.created_at


# region Top Level Resources

class Blueprint(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'blueprints'
    __table_args__ = (
        db.Index(
            'blueprints_id__tenant_id_idx',
            'id', '_tenant_id',
            unique=True
        ),
    )

    skipped_fields = dict(
        SQLResourceBase.skipped_fields,
        v1=['main_file_name', 'description']
    )

    main_file_name = db.Column(db.Text, nullable=False)
    plan = db.Column(db.PickleType(protocol=2), nullable=False)
    updated_at = db.Column(UTCDateTime)
    description = db.Column(db.Text)
    is_hidden = db.Column(db.Boolean, nullable=False, default=False)


class Snapshot(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'snapshots'
    __table_args__ = (
        db.Index(
            'snapshots_id__tenant_id_idx',
            'id', '_tenant_id',
            unique=True
        ),
    )

    status = db.Column(db.Enum(*SnapshotState.STATES, name='snapshot_status'))
    error = db.Column(db.Text)


class Plugin(SQLResourceBase):
    __tablename__ = 'plugins'
    __table_args__ = (
        db.Index(
            'plugins_name_version__tenant_id_idx',
            'package_name', 'package_version', '_tenant_id',
            unique=True
        ),
    )

    archive_name = db.Column(db.Text, nullable=False, index=True)
    distribution = db.Column(db.Text)
    distribution_release = db.Column(db.Text)
    distribution_version = db.Column(db.Text)
    excluded_wheels = db.Column(db.PickleType(protocol=2))
    package_name = db.Column(db.Text, nullable=False, index=True)
    package_source = db.Column(db.Text)
    package_version = db.Column(db.Text)
    supported_platform = db.Column(db.PickleType(protocol=2))
    supported_py_versions = db.Column(db.PickleType(protocol=2))
    uploaded_at = db.Column(UTCDateTime, nullable=False, index=True)
    wheels = db.Column(db.PickleType(protocol=2), nullable=False)

    def yaml_file_path(self):
        plugin_dir = path.join(config.instance.file_server_root,
                               FILE_SERVER_PLUGINS_FOLDER,
                               self.id)
        if not path.isdir(plugin_dir):
            return None
        yaml_files = files_in_folder(plugin_dir, '*.yaml')
        return yaml_files[0] if yaml_files else None

    def _yaml_file_name(self):
        yaml_path = self.yaml_file_path()
        return path.basename(yaml_path) if yaml_path else ''

    @property
    def file_server_path(self):
        file_name = self._yaml_file_name()
        if not file_name:
            return ''
        return path.join(FILE_SERVER_RESOURCES_FOLDER,
                         FILE_SERVER_PLUGINS_FOLDER,
                         self.id,
                         file_name)

    @property
    def yaml_url_path(self):
        if not self._yaml_file_name():
            return ''
        return 'plugin:{0}?version={1}&distribution={2}'.format(
            self.package_name,
            self.package_version,
            self.distribution
        )

    @classproperty
    def response_fields(cls):
        fields = super(Plugin, cls).response_fields
        fields['file_server_path'] = flask_fields.String
        fields['yaml_url_path'] = flask_fields.String
        return fields

    def to_response(self, get_data=False, **kwargs):
        plugin_dict = super(Plugin, self).to_response()
        if not get_data:
            plugin_dict['file_server_path'] = ''
        return plugin_dict


class Secret(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'secrets'
    __table_args__ = (
        db.Index(
            'secrets_id_tenant_id_idx',
            'id', '_tenant_id',
            unique=True
        ),
    )

    value = db.Column(db.Text)
    updated_at = db.Column(UTCDateTime)
    is_hidden_value = db.Column(db.Boolean, nullable=False, default=False)

    @hybrid_property
    def key(self):
        return self.id

    @classproperty
    def resource_fields(cls):
        fields = super(Secret, cls).resource_fields
        fields['key'] = fields.pop('id')
        return fields


class Site(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'sites'
    __table_args__ = (
        db.Index(
            'site_name__tenant_id_idx',
            'name', '_tenant_id',
            unique=True
        ),
    )

    name = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    _extra_fields = {
        'location': flask_fields.String
    }

    @property
    def location(self):
        if (self.latitude is None) or (self.longitude is None):
            return None
        return "{0}, {1}".format(self.latitude, self.longitude)

    @classproperty
    def response_fields(cls):
        fields = super(Site, cls).response_fields
        fields.pop('id')
        return fields

# endregion

# region Derived Resources


class Deployment(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'deployments'
    __table_args__ = (
        db.Index(
            'deployments__site_fk_visibility_idx',
            '_blueprint_fk', '_site_fk', 'visibility', '_tenant_id'
        ),
        db.Index(
            'deployments_id__tenant_id_idx',
            'id', '_tenant_id',
            unique=True
        ),
    )
    skipped_fields = dict(
        SQLResourceBase.skipped_fields,
        v1=['scaling_groups'],
        v2=['scaling_groups']
    )

    description = db.Column(db.Text)
    inputs = db.Column(db.PickleType(protocol=2))
    groups = db.Column(db.PickleType(protocol=2))
    permalink = db.Column(db.Text)
    policy_triggers = db.Column(db.PickleType(protocol=2))
    policy_types = db.Column(db.PickleType(protocol=2))
    outputs = db.Column(db.PickleType(protocol=2, comparator=lambda *a: False))
    capabilities = db.Column(db.PickleType(
        protocol=2, comparator=lambda *a: False))
    scaling_groups = db.Column(db.PickleType(protocol=2))
    updated_at = db.Column(UTCDateTime)
    workflows = db.Column(db.PickleType(
        protocol=2, comparator=lambda *a: False))
    runtime_only_evaluation = db.Column(db.Boolean, default=False)

    _blueprint_fk = foreign_key(Blueprint._storage_id)
    _site_fk = foreign_key(Site._storage_id,
                           nullable=True,
                           ondelete='SET NULL')

    @declared_attr
    def blueprint(cls):
        return one_to_many_relationship(cls, Blueprint, cls._blueprint_fk)

    blueprint_id = association_proxy('blueprint', 'id')

    @declared_attr
    def site(cls):
        return one_to_many_relationship(cls, Site, cls._site_fk, cascade=False)

    site_name = association_proxy('site', 'name')

    @classproperty
    def response_fields(cls):
        fields = super(Deployment, cls).response_fields
        fields['workflows'] = flask_fields.List(
            flask_fields.Nested(Workflow.resource_fields)
        )
        return fields

    def to_response(self, **kwargs):
        dep_dict = super(Deployment, self).to_response()
        dep_dict['workflows'] = self._list_workflows(self.workflows)
        return dep_dict

    @staticmethod
    def _list_workflows(deployment_workflows):
        if deployment_workflows is None:
            return None

        return [Workflow(name=wf_name,
                         created_at=None,
                         plugin=wf.get('plugin', ''),
                         operation=wf.get('operation', ''),
                         parameters=wf.get('parameters', dict()))
                for wf_name, wf in deployment_workflows.items()]


class Execution(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'executions'
    STATUS_DISPLAY_NAMES = {
        ExecutionState.TERMINATED: 'completed'
    }
    _extra_fields = {
        'status_display': flask_fields.String
    }
    __table_args__ = (
        db.Index(
            'executions_dep_fk_isw_vis_tenant_id_idx',
            '_deployment_fk', 'is_system_workflow', 'visibility', '_tenant_id'
        ),
    )

    ended_at = db.Column(UTCDateTime, nullable=True, index=True)
    error = db.Column(db.Text)
    is_system_workflow = db.Column(db.Boolean, nullable=False, index=True)
    parameters = db.Column(db.PickleType(protocol=2))
    status = db.Column(
        db.Enum(*ExecutionState.STATES, name='execution_status')
    )
    workflow_id = db.Column(db.Text, nullable=False)
    started_at = db.Column(UTCDateTime, nullable=True)
    scheduled_for = db.Column(UTCDateTime, nullable=True)
    is_dry_run = db.Column(db.Boolean, nullable=False, default=False)
    token = db.Column(db.String(100), nullable=True, index=True)

    _deployment_fk = foreign_key(Deployment._storage_id, nullable=True)

    @declared_attr
    def deployment(cls):
        return one_to_many_relationship(cls, Deployment, cls._deployment_fk)

    deployment_id = association_proxy('deployment', 'id')
    blueprint_id = db.Column(db.Text, nullable=True)

    @hybrid_property
    def status_display(self):
        status = self.status
        return self.STATUS_DISPLAY_NAMES.get(status, status)

    @status_display.expression
    def status_display(cls):
        table = cls.__table__
        cases = [
            (table.c.status == status, label)
            for status, label in cls.STATUS_DISPLAY_NAMES.items()
        ]
        return case(cases, else_=db.cast(table.c.status, db.Text))

    def _get_identifier_dict(self):
        id_dict = super(Execution, self)._get_identifier_dict()
        id_dict['status'] = self.status
        return id_dict

    def set_deployment(self, deployment, blueprint_id=None):
        self._set_parent(deployment)
        self.deployment = deployment
        current_blueprint_id = blueprint_id or deployment.blueprint_id
        self.blueprint_id = current_blueprint_id

    @classproperty
    def resource_fields(cls):
        fields = super(Execution, cls).resource_fields
        fields.pop('token')
        return fields


class Event(SQLResourceBase):
    """Execution events."""
    __tablename__ = 'events'
    __table_args__ = (
        db.Index(
            'events_node_id_visibility_idx',
            'node_id', 'visibility'
        ),
    )
    timestamp = db.Column(
        UTCDateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    reported_timestamp = db.Column(UTCDateTime, nullable=False)
    message = db.Column(db.Text)
    message_code = db.Column(db.Text)
    event_type = db.Column(db.Text)
    operation = db.Column(db.Text)
    node_id = db.Column(db.Text, index=True)
    source_id = db.Column(db.Text)
    target_id = db.Column(db.Text)
    error_causes = db.Column(JSONString)

    _execution_fk = foreign_key(Execution._storage_id)

    @classmethod
    def default_sort_column(cls):
        return cls.reported_timestamp

    @declared_attr
    def execution(cls):
        return one_to_many_relationship(cls, Execution, cls._execution_fk)

    execution_id = association_proxy('execution', 'id')

    def set_execution(self, execution):
        self._set_parent(execution)
        self.execution = execution


class Log(SQLResourceBase):
    """Execution logs."""
    __tablename__ = 'logs'
    __table_args__ = (
        db.Index(
            'logs_node_id_visibility_execution_fk_idx',
            'node_id', 'visibility', '_execution_fk'
        ),
    )

    timestamp = db.Column(
        UTCDateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    reported_timestamp = db.Column(UTCDateTime, nullable=False)
    message = db.Column(db.Text)
    message_code = db.Column(db.Text)
    logger = db.Column(db.Text)
    level = db.Column(db.Text)
    operation = db.Column(db.Text)
    node_id = db.Column(db.Text, index=True)
    source_id = db.Column(db.Text)
    target_id = db.Column(db.Text)

    _execution_fk = foreign_key(Execution._storage_id)

    @classmethod
    def default_sort_column(cls):
        return cls.reported_timestamp

    @declared_attr
    def execution(cls):
        return one_to_many_relationship(cls, Execution, cls._execution_fk)

    execution_id = association_proxy('execution', 'id')

    def set_execution(self, execution):
        self._set_parent(execution)
        self.execution = execution


class PluginsUpdate(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'plugins_updates'

    state = db.Column(db.Text)
    deployments_to_update = db.Column(db.PickleType(protocol=2))
    forced = db.Column(db.Boolean, default=False)

    _original_blueprint_fk = foreign_key(Blueprint._storage_id)
    _temp_blueprint_fk = foreign_key(Blueprint._storage_id,
                                     nullable=True,
                                     ondelete='SET NULL')
    _execution_fk = foreign_key(Execution._storage_id,
                                nullable=True,
                                ondelete='SET NULL')

    @declared_attr
    def execution(cls):
        return one_to_many_relationship(cls, Execution, cls._execution_fk)

    @declared_attr
    def blueprint(cls):
        return one_to_many_relationship(
            cls,
            Blueprint,
            cls._original_blueprint_fk,
            backreference='original_of_plugins_update')

    @declared_attr
    def temp_blueprint(cls):
        return one_to_many_relationship(cls,
                                        Blueprint,
                                        cls._temp_blueprint_fk,
                                        backreference='temp_of_plugins_update',
                                        cascade=False)

    blueprint_id = association_proxy('blueprint', 'id')
    temp_blueprint_id = association_proxy('temp_blueprint', 'id')
    execution_id = association_proxy('execution', 'id')

    def set_blueprint(self, blueprint):
        self._set_parent(blueprint)
        self.blueprint = blueprint


class DeploymentUpdate(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'deployment_updates'

    deployment_plan = db.Column(db.PickleType(protocol=2))
    deployment_update_node_instances = db.Column(db.PickleType(protocol=2))
    deployment_update_deployment = db.Column(db.PickleType(protocol=2))
    central_plugins_to_uninstall = db.Column(db.PickleType(protocol=2))
    central_plugins_to_install = db.Column(db.PickleType(protocol=2))
    deployment_update_nodes = db.Column(db.PickleType(protocol=2))
    modified_entity_ids = db.Column(db.PickleType(protocol=2))
    old_inputs = db.Column(db.PickleType(protocol=2))
    new_inputs = db.Column(db.PickleType(protocol=2))
    state = db.Column(db.Text)
    runtime_only_evaluation = db.Column(db.Boolean, default=False)
    keep_old_deployment_dependencies = db.Column(
        db.Boolean, nullable=False, default=False)

    _execution_fk = foreign_key(Execution._storage_id, nullable=True)
    _deployment_fk = foreign_key(Deployment._storage_id)
    _old_blueprint_fk = foreign_key(Blueprint._storage_id, nullable=True)
    _new_blueprint_fk = foreign_key(Blueprint._storage_id, nullable=True)

    preview = False

    @declared_attr
    def execution(cls):
        return one_to_many_relationship(cls, Execution, cls._execution_fk)

    @declared_attr
    def deployment(cls):
        return one_to_many_relationship(cls, Deployment, cls._deployment_fk)

    @declared_attr
    def old_blueprint(cls):
        return one_to_many_relationship(cls,
                                        Blueprint,
                                        cls._old_blueprint_fk,
                                        backreference='update_from',
                                        cascade=False)

    @declared_attr
    def new_blueprint(cls):
        return one_to_many_relationship(cls,
                                        Blueprint,
                                        cls._new_blueprint_fk,
                                        backreference='update_to',
                                        cascade=False)

    deployment_id = association_proxy('deployment', 'id')
    execution_id = association_proxy('execution', 'id')
    old_blueprint_id = association_proxy('old_blueprint', 'id')
    new_blueprint_id = association_proxy('new_blueprint', 'id')

    @classproperty
    def response_fields(cls):
        fields = super(DeploymentUpdate, cls).response_fields
        fields['steps'] = flask_fields.List(
            flask_fields.Nested(DeploymentUpdateStep.response_fields)
        )
        return fields

    def to_response(self, **kwargs):
        dep_update_dict = super(DeploymentUpdate, self).to_response()
        # Taking care of the fact the DeploymentSteps are objects
        dep_update_dict['steps'] = [step.to_dict() for step in self.steps]
        return dep_update_dict

    def set_deployment(self, deployment):
        self._set_parent(deployment)
        self.deployment = deployment


class DeploymentUpdateStep(SQLResourceBase):
    __tablename__ = 'deployment_update_steps'

    action = db.Column(db.Enum(*ACTION_TYPES, name='action_type'))
    entity_id = db.Column(db.Text, nullable=False)
    entity_type = db.Column(db.Enum(*ENTITY_TYPES, name='entity_type'))

    _deployment_update_fk = foreign_key(DeploymentUpdate._storage_id)

    @declared_attr
    def deployment_update(cls):
        return one_to_many_relationship(cls,
                                        DeploymentUpdate,
                                        cls._deployment_update_fk,
                                        backreference='steps')

    deployment_update_id = association_proxy('deployment_update', 'id')

    def set_deployment_update(self, deployment_update):
        self._set_parent(deployment_update)
        self.deployment_update = deployment_update


class DeploymentModification(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'deployment_modifications'

    context = db.Column(db.PickleType(protocol=2))
    ended_at = db.Column(UTCDateTime, index=True)
    modified_nodes = db.Column(db.PickleType(protocol=2))
    node_instances = db.Column(db.PickleType(protocol=2))
    status = db.Column(db.Enum(
        *DeploymentModificationState.STATES,
        name='deployment_modification_status'
    ))

    _deployment_fk = foreign_key(Deployment._storage_id)

    @declared_attr
    def deployment(cls):
        return one_to_many_relationship(cls,
                                        Deployment,
                                        cls._deployment_fk,
                                        backreference='modifications')

    deployment_id = association_proxy('deployment', 'id')

    def set_deployment(self, deployment):
        self._set_parent(deployment)
        self.deployment = deployment


class Node(SQLResourceBase):
    __tablename__ = 'nodes'

    is_id_unique = False
    skipped_fields = dict(
        SQLResourceBase.skipped_fields,
        v1=['max_number_of_instances', 'min_number_of_instances'],
        v2=['max_number_of_instances', 'min_number_of_instances']
    )

    deploy_number_of_instances = db.Column(db.Integer, nullable=False)
    # TODO: This probably should be a foreign key, but there's no guarantee
    # in the code, currently, that the host will be created beforehand
    host_id = db.Column(db.Text)
    max_number_of_instances = db.Column(db.Integer, nullable=False)
    min_number_of_instances = db.Column(db.Integer, nullable=False)
    number_of_instances = db.Column(db.Integer, nullable=False)
    planned_number_of_instances = db.Column(db.Integer, nullable=False)
    plugins = db.Column(db.PickleType(protocol=2))
    plugins_to_install = db.Column(db.PickleType(protocol=2))
    properties = db.Column(db.PickleType(protocol=2))
    relationships = db.Column(db.PickleType(protocol=2))
    operations = db.Column(db.PickleType(protocol=2))
    type = db.Column(db.Text, nullable=False, index=True)
    type_hierarchy = db.Column(db.PickleType(protocol=2))

    _deployment_fk = foreign_key(Deployment._storage_id)

    # These are for fixing a bug where wrong number of instances was returned
    # for deployments with group scaling policy
    _extra_fields = {
        'actual_number_of_instances': flask_fields.Integer,
        'actual_planned_number_of_instances': flask_fields.Integer,
    }
    actual_planned_number_of_instances = 0

    instances = db.relationship('NodeInstance', lazy='subquery')

    @hybrid_property
    def actual_number_of_instances(self):
        return len(self.instances)

    @actual_number_of_instances.expression
    def actual_number_of_instances(cls):
        ni_table = table('node_instances', column('id'), column('_node_fk'))
        return (select([func.count(ni_table.c.id)]).
                where(ni_table.c._node_fk == cls._storage_id).
                label("actual_number_of_instances"))

    @declared_attr
    def deployment(cls):
        return one_to_many_relationship(cls, Deployment, cls._deployment_fk)

    deployment_id = association_proxy('deployment', 'id')
    blueprint_id = association_proxy('deployment', 'blueprint_id')

    def to_dict(self, suppress_error=False):
        # some usages of the dict want 'name' instead of 'id' (notably,
        # function evaluation in the dsl-parser)
        d = super(Node, self).to_dict(suppress_error)
        d['name'] = d['id']
        return d

    def set_deployment(self, deployment):
        self._set_parent(deployment)
        self.deployment = deployment

    def set_actual_planned_node_instances(self, num):
        self.actual_planned_number_of_instances = num


class NodeInstance(SQLResourceBase):
    __tablename__ = 'node_instances'
    __table_args__ = (
        db.Index(
            'node_instances_state_visibility_idx',
            'state', 'visibility'
        ),
    )
    skipped_fields = dict(
        SQLResourceBase.skipped_fields,
        v1=['scaling_groups'],
        v2=['scaling_groups']
    )

    # TODO: This probably should be a foreign key, but there's no guarantee
    # in the code, currently, that the host will be created beforehand
    host_id = db.Column(db.Text)
    index = db.Column(db.Integer)
    relationships = db.Column(db.PickleType(protocol=2))
    runtime_properties = db.Column(db.PickleType(protocol=2))
    scaling_groups = db.Column(db.PickleType(protocol=2))
    state = db.Column(db.Text, nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)

    # This automatically increments the version on each update
    __mapper_args__ = {'version_id_col': version}

    _node_fk = foreign_key(Node._storage_id)

    @declared_attr
    def node(cls):
        return one_to_many_relationship(cls, Node, cls._node_fk)

    node_id = association_proxy('node', 'id')
    deployment_id = association_proxy('node', 'deployment_id')

    def set_node(self, node):
        self._set_parent(node)
        self.node = node


class Agent(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'agents'

    ip = db.Column(db.Text)
    name = db.Column(db.Text, nullable=False)
    install_method = db.Column(db.Text, nullable=False)
    system = db.Column(db.Text)
    version = db.Column(db.Text, nullable=False)
    state = db.Column(db.Enum(*AgentState.STATES, name='agent_states'),
                      default=AgentState.CREATING, nullable=False)
    rabbitmq_username = db.Column(db.Text)
    rabbitmq_password = db.Column(db.Text)
    rabbitmq_exchange = db.Column(db.Text, nullable=False)
    updated_at = db.Column(UTCDateTime)

    _node_instance_fk = foreign_key(NodeInstance._storage_id)

    # The following fields for backwards compatibility with the REST API:
    # agents.list() pre-dated the Agents table in the DB
    _extra_fields = {
        'host_id': flask_fields.String,
        'node': flask_fields.String,
        'deployment': flask_fields.String,
        'node_ids': flask_fields.String,
        'node_instance_ids': flask_fields.String,
        'install_methods': flask_fields.String
    }

    @declared_attr
    def node_instance(cls):
        # When upgrading an agent we want to save both the old and new agents
        # with the same node_instance_id
        return one_to_many_relationship(cls,
                                        NodeInstance,
                                        cls._node_instance_fk)

    node_instance_id = association_proxy('node_instance', 'id')
    node_id = association_proxy('node_instance', 'node_id')
    deployment_id = association_proxy('node_instance', 'deployment_id')

    node = node_id
    deployment = deployment_id
    node_ids = node_id
    node_instance_ids = node_instance_id

    @property
    def host_id(self):
        return self.node_instance_id

    @hybrid_property
    def install_methods(self):
        return self.install_method

    def set_node_instance(self, node_instance):
        self._set_parent(node_instance)
        self.node_instance = node_instance

    def to_response(self, **kwargs):
        agent_dict = super(Agent, self).to_response()
        agent_dict.pop('rabbitmq_username')
        agent_dict.pop('rabbitmq_password')
        return agent_dict


class TasksGraph(SQLResourceBase):
    __tablename__ = 'tasks_graphs'
    __table_args__ = (
        db.Index(
            'tasks_graphs__execution_fk_name_visibility_idx',
            '_execution_fk', 'name', 'visibility',
            unique=True
        ),
    )

    name = db.Column(db.Text, index=True)
    created_at = db.Column(UTCDateTime, nullable=False, index=True)

    _execution_fk = foreign_key(Execution._storage_id)

    @declared_attr
    def execution(cls):
        return one_to_many_relationship(cls, Execution, cls._execution_fk)

    execution_id = association_proxy('execution', 'id')


class Operation(SQLResourceBase):
    __tablename__ = 'operations'

    name = db.Column(db.Text)
    state = db.Column(db.Text, nullable=False)
    created_at = db.Column(UTCDateTime, nullable=False, index=True)

    dependencies = db.Column(db.ARRAY(db.Text))
    type = db.Column(db.Text)
    parameters = db.Column(JSONString)

    _tasks_graph_fk = foreign_key(TasksGraph._storage_id)

    @declared_attr
    def tasks_graph(cls):
        return one_to_many_relationship(cls, TasksGraph, cls._tasks_graph_fk)


class InterDeploymentDependencies(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'inter_deployment_dependencies'

    dependency_creator = db.Column(db.Text, nullable=False)
    _source_deployment = foreign_key(Deployment._storage_id)
    _target_deployment = foreign_key(Deployment._storage_id,
                                     nullable=True,
                                     ondelete='SET NULL')
    __table_args__ = (
        UniqueConstraint(
            'dependency_creator',
            '_source_deployment',
            '_tenant_id',
            name='inter_deployment_uc'),
    )

    @declared_attr
    def source_deployment(cls):
        return one_to_many_relationship(
            cls,
            Deployment,
            cls._source_deployment,
            backreference='source_of_dependency_in')

    @declared_attr
    def target_deployment(cls):
        return one_to_many_relationship(
            cls,
            Deployment,
            cls._target_deployment,
            backreference='target_of_dependency_in')

    source_deployment_id = association_proxy('source_deployment', 'id')
    target_deployment_id = association_proxy('target_deployment', 'id')
# endregion

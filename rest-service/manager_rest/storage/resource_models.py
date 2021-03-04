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

from sqlalchemy import case
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import func, select, table, column
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.associationproxy import association_proxy

from cloudify.models_states import (AgentState,
                                    SnapshotState,
                                    ExecutionState,
                                    DeploymentModificationState,
                                    DeploymentState)

from manager_rest import config
from manager_rest.rest.responses import Workflow, Label
from manager_rest.utils import (get_rrule,
                                classproperty,
                                files_in_folder)
from manager_rest.deployment_update.constants import ACTION_TYPES, ENTITY_TYPES
from manager_rest.constants import (FILE_SERVER_PLUGINS_FOLDER,
                                    FILE_SERVER_RESOURCES_FOLDER)

from .models_base import (
    db,
    JSONString,
    UTCDateTime,
)
from .management_models import User
from .resource_models_base import SQLResourceBase, SQLModelBase
from .relationships import (
    foreign_key,
    one_to_many_relationship,
    many_to_many_relationship
)


RELATIONSHIP = 'relationship'
NODE = 'node'


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

    main_file_name = db.Column(db.Text)
    plan = db.Column(db.PickleType(protocol=2))
    updated_at = db.Column(UTCDateTime)
    description = db.Column(db.Text)
    is_hidden = db.Column(db.Boolean, nullable=False, default=False)
    state = db.Column(db.Text)
    error = db.Column(db.Text)
    error_traceback = db.Column(db.Text)
    _upload_execution_fk = foreign_key('executions._storage_id',
                                       nullable=True,
                                       ondelete='SET NULL',
                                       deferrable=True,
                                       initially='DEFERRED',
                                       use_alter=True)

    @classproperty
    def labels_model(cls):
        return BlueprintLabel

    @declared_attr
    def labels(cls):
        # labels are defined as `backref` in DeploymentsLabel model
        return None

    @declared_attr
    def upload_execution(cls):
        return db.relationship('Execution',
                               foreign_keys=[cls._upload_execution_fk],
                               cascade='all, delete')

    @classproperty
    def response_fields(cls):
        fields = super(Blueprint, cls).response_fields
        fields['labels'] = flask_fields.List(
            flask_fields.Nested(Label.resource_fields))
        return fields

    @classproperty
    def allowed_filter_attrs(cls):
        return ['created_by']

    def to_response(self, **kwargs):
        blueprint_dict = super(Blueprint, self).to_response()
        blueprint_dict['labels'] = self.list_labels(self.labels)
        return blueprint_dict


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
            'package_name', 'package_version', '_tenant_id', 'distribution',
            'distribution_release', 'distribution_version',
            unique=True
        ),
    )
    _extra_fields = {'installation_state': flask_fields.Raw}

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
    title = db.Column(db.Text)

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
        if 'installation_state' in plugin_dict:
            plugin_dict['installation_state'] = [
                s.to_dict() for s in plugin_dict['installation_state']]
        return plugin_dict

    @declared_attr
    def installation_state(cls):
        return db.relationship('_PluginState', cascade='delete',
                               passive_deletes=True)


class _PluginState(SQLModelBase):
    __tablename__ = 'plugins_states'
    _extra_fields = {'manager': flask_fields.Raw}

    _storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    _plugin_fk = foreign_key(Plugin._storage_id)
    _manager_fk = foreign_key('managers.id', nullable=True)
    _agent_fk = foreign_key('agents._storage_id', nullable=True)
    state = db.Column(db.Text)
    error = db.Column(db.Text)

    @classmethod
    def unique_id(cls):
        return '_storage_id'

    def __repr__(self):
        return '<PluginState plugin={0} state={1}>'.format(
            self._plugin_fk, self.state)

    def to_dict(self, suppress_error=False):
        rv = super(_PluginState, self).to_dict(suppress_error)
        rv['manager'] = self.manager.hostname if self.manager else None
        rv['agent'] = self.agent.name if self.agent else None
        return rv

    @declared_attr
    def manager(cls):
        return db.relationship('Manager', lazy='joined')

    @declared_attr
    def agent(cls):
        return db.relationship('Agent', lazy='joined')


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
    installation_status = db.Column(db.Enum(
        DeploymentState.ACTIVE,
        DeploymentState.INACTIVE,
        name="installation_status"
    ))
    deployment_status = db.Column(db.Enum(
            DeploymentState.GOOD,
            DeploymentState.IN_PROGRESS,
            DeploymentState.REQUIRE_ATTENTION,
            name='deployment_status'
        )
    )
    _blueprint_fk = foreign_key(Blueprint._storage_id)
    _site_fk = foreign_key(Site._storage_id,
                           nullable=True,
                           ondelete='SET NULL')
    _create_execution_fk = foreign_key('executions._storage_id',
                                       nullable=True,
                                       ondelete='SET NULL',
                                       deferrable=True,
                                       initially='DEFERRED',
                                       use_alter=True)

    _latest_execution_fk = foreign_key('executions._storage_id',
                                       nullable=True,
                                       ondelete='SET NULL',
                                       deferrable=True,
                                       initially='DEFERRED',
                                       use_alter=True)

    @classproperty
    def labels_model(cls):
        return DeploymentLabel

    @declared_attr
    def create_execution(cls):
        """The create-deployment-environment execution for this deployment"""
        return db.relationship('Execution',
                               foreign_keys=[cls._create_execution_fk],
                               cascade='all, delete',
                               post_update=True)

    @declared_attr
    def latest_execution(cls):
        return db.relationship('Execution',
                               foreign_keys=[cls._latest_execution_fk],
                               cascade='all, delete',
                               post_update=True)

    @declared_attr
    def blueprint(cls):
        return one_to_many_relationship(cls, Blueprint, cls._blueprint_fk)

    blueprint_id = association_proxy('blueprint', 'id')

    @declared_attr
    def site(cls):
        return one_to_many_relationship(cls, Site, cls._site_fk, cascade=False)

    site_name = association_proxy('site', 'name')

    @declared_attr
    def labels(cls):
        # labels are defined as `backref` in DeploymentsLabel model
        return None

    @classproperty
    def response_fields(cls):
        fields = super(Deployment, cls).response_fields
        fields['workflows'] = flask_fields.List(
            flask_fields.Nested(Workflow.resource_fields)
        )
        fields['labels'] = flask_fields.List(
            flask_fields.Nested(Label.resource_fields))
        fields['deployment_groups'] = flask_fields.List(flask_fields.String)
        fields['latest_execution_status'] = flask_fields.String()
        return fields

    @classproperty
    def allowed_filter_attrs(cls):
        return ['blueprint_id', 'created_by', 'site_name']

    def to_response(self, **kwargs):
        dep_dict = super(Deployment, self).to_response()
        dep_dict['workflows'] = self._list_workflows(self.workflows)
        dep_dict['labels'] = self.list_labels(self.labels)
        dep_dict['deployment_groups'] = [g.id for g in self.deployment_groups]
        dep_dict['latest_execution_status'] = self.latest_execution_status
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

    @property
    def latest_execution_status(self):
        _execution = self.latest_execution or self.create_execution
        if not _execution:
            return None
        return DeploymentState.EXECUTION_STATES_SUMMARY.get(_execution.status)

    def evaluate_deployment_status(self):
        """
        Evaluate the overall deployment status based on installation status
        and latest execution object
        :return: deployment_status: Overall deployment status
        """
        # TODO we need to cover also aggregated statuses for deployment
        #  children later on
        if self.latest_execution_status == DeploymentState.CANCELLED:
            if self.installation_status == DeploymentState.ACTIVE:
                return DeploymentState.GOOD
            return DeploymentState.REQUIRE_ATTENTION
        elif self.latest_execution_status == DeploymentState.IN_PROGRESS and \
                self.installation_status == DeploymentState.INACTIVE:
            return DeploymentState.IN_PROGRESS
        elif self.latest_execution_status == DeploymentState.FAILED or \
                self.installation_status == DeploymentState.INACTIVE:
            return DeploymentState.REQUIRE_ATTENTION
        elif self.latest_execution_status == DeploymentState.COMPLETED and \
                self.installation_status == DeploymentState.ACTIVE:
            return DeploymentState.GOOD
        else:
            return DeploymentState.IN_PROGRESS


class DeploymentGroup(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'deployment_groups'
    description = db.Column(db.Text)
    default_inputs = db.Column(JSONString)
    _default_blueprint_fk = foreign_key(
        Blueprint._storage_id,
        ondelete='SET NULL',
        nullable=True)

    @declared_attr
    def default_blueprint(cls):
        return one_to_many_relationship(
            cls, Blueprint, cls._default_blueprint_fk)

    @declared_attr
    def deployments(cls):
        return many_to_many_relationship(cls, Deployment)

    @property
    def deployment_ids(self):
        return [dep.id for dep in self.deployments]

    @property
    def default_blueprint_id(self):
        if not self.default_blueprint:
            return None
        return self.default_blueprint.id

    @classproperty
    def response_fields(cls):
        fields = super(DeploymentGroup, cls).response_fields
        fields['deployment_ids'] = flask_fields.List(
            flask_fields.String()
        )
        fields['default_blueprint_id'] = flask_fields.String()
        return fields


class _Label(CreatedAtMixin, SQLModelBase):
    """An abstract class for the different labels models."""
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.Text, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False, index=True)

    labeled_model = None

    @declared_attr
    def _creator_id(cls):
        return foreign_key(User.id)

    @declared_attr
    def creator(cls):
        return one_to_many_relationship(cls, User, cls._creator_id, 'id')

    @declared_attr
    def visibility(cls):
        return cls.labeled_model.visibility

    @declared_attr
    def _tenant_id(cls):
        return cls.labeled_model._tenant_id


class DeploymentLabel(_Label):
    __tablename__ = 'deployments_labels'
    __table_args__ = (
        db.UniqueConstraint(
            'key', 'value', '_labeled_model_fk'),
    )
    labeled_model = Deployment

    _labeled_model_fk = foreign_key(Deployment._storage_id)

    @declared_attr
    def deployment(cls):
        return db.relationship(
            'Deployment', lazy='joined',
            backref=db.backref('labels', cascade='all, delete-orphan'))


class BlueprintLabel(_Label):
    __tablename__ = 'blueprints_labels'
    __table_args__ = (
        db.UniqueConstraint(
            'key', 'value', '_labeled_model_fk'),
    )
    labeled_model = Blueprint

    _labeled_model_fk = foreign_key(Blueprint._storage_id)

    @declared_attr
    def blueprint(cls):
        return db.relationship(
            'Blueprint', lazy='joined',
            backref=db.backref('labels', cascade='all, delete-orphan'))


class Filter(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'filters'
    __table_args__ = (
        db.Index(
            'filters_id__tenant_id_idx',
            'id', '_tenant_id',
            unique=True
        ),
    )
    _extra_fields = {'labels_filters': flask_fields.Raw}

    value = db.Column(JSONString, nullable=True)
    filtered_resource = db.Column(db.Text, nullable=False, index=True)
    updated_at = db.Column(UTCDateTime)

    @property
    def labels_filters(self):
        return [filter_rule for filter_rule in self.value
                if filter_rule['type'] == 'label']


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
        return one_to_many_relationship(
            cls, Deployment, cls._deployment_fk,
            backref=db.backref(
                'executions', passive_deletes=True, cascade='all'))

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


class ExecutionGroup(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'execution_groups'
    _deployment_group_fk = foreign_key(
        DeploymentGroup._storage_id, nullable=True)
    workflow_id = db.Column(db.Text, nullable=False)

    @declared_attr
    def deployment_group(cls):
        return one_to_many_relationship(
            cls, DeploymentGroup, cls._deployment_group_fk)

    deployment_group_id = association_proxy('deployment_group', 'id')

    @declared_attr
    def executions(cls):
        return many_to_many_relationship(
            cls, Execution,
            ondelete='CASCADE'
        )

    @property
    def execution_ids(self):
        return [exc.id for exc in self.executions]

    @classproperty
    def response_fields(cls):
        fields = super(ExecutionGroup, cls).response_fields
        fields['execution_ids'] = flask_fields.List(
            flask_fields.String()
        )
        fields['deployment_group_id'] = flask_fields.String()
        fields['status'] = flask_fields.String()
        return fields

    @property
    def status(self):
        """Status of this group, based on the status of its executions.

        The group status is:
            - pending, if all executions are pending
            - started, if some executions are already not pending, and not
                all are finished yet
            - failed, if all executions are finished, and some have failed
            - terminated, if all are finished, and none have failed (but
                some might have been cancelled)
        """
        states = {e.status for e in self.executions}

        if all(s == ExecutionState.PENDING for s in states):
            return ExecutionState.PENDING

        if all(s in ExecutionState.END_STATES for s in states):
            if ExecutionState.FAILED in states:
                return ExecutionState.FAILED
            return ExecutionState.TERMINATED

        return ExecutionState.STARTED

    def to_response(self, get_data=False, **kwargs):
        if get_data:
            skip_fields = []
        else:
            skip_fields = ['execution_ids', 'status']
        return {
            f: getattr(self, f)
            for f in self.response_fields if f not in skip_fields
        }


class ExecutionSchedule(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'execution_schedules'
    __table_args__ = (
        db.UniqueConstraint(
            'id', '_deployment_fk', '_tenant_id'),
        db.Index(
            'execution_schedules_id__deployment_fk_idx',
            'id', '_deployment_fk', '_tenant_id',
            unique=True
        ),
    )
    is_id_unique = False

    next_occurrence = db.Column(UTCDateTime, nullable=True, index=True)
    since = db.Column(UTCDateTime, nullable=True)
    until = db.Column(UTCDateTime, nullable=True)
    rule = db.Column(JSONString(), nullable=False)
    slip = db.Column(db.Integer, nullable=False)
    workflow_id = db.Column(db.Text, nullable=False)
    parameters = db.Column(JSONString())
    execution_arguments = db.Column(JSONString())
    stop_on_fail = db.Column(db.Boolean, nullable=False, default=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)

    _deployment_fk = foreign_key(Deployment._storage_id)
    _latest_execution_fk = foreign_key(Execution._storage_id, nullable=True)

    deployment_id = association_proxy('deployment', 'id')
    latest_execution_status = association_proxy('latest_execution', 'status')

    @declared_attr
    def deployment(cls):
        return one_to_many_relationship(cls, Deployment, cls._deployment_fk)

    @declared_attr
    def latest_execution(cls):
        return one_to_many_relationship(cls, Execution,
                                        cls._latest_execution_fk)

    def compute_next_occurrence(self):
        return get_rrule(self.rule,
                         self.since,
                         self.until).after(datetime.utcnow())

    @property
    def all_next_occurrences(self, pagination_size=1000):
        next_occurrences = []
        search_limit = 100000
        for i, d in enumerate(get_rrule(self.rule, self.since, self.until)):
            if i >= search_limit or len(next_occurrences) >= pagination_size:
                break
            if d >= datetime.utcnow():
                next_occurrences.append(d.strftime("%Y-%m-%d %H:%M:%S"))
        return next_occurrences

    @classproperty
    def response_fields(cls):
        fields = super(ExecutionSchedule, cls).response_fields
        fields['all_next_occurrences'] = \
            flask_fields.List(flask_fields.String())
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
            backref=db.backref('original_of_plugins_update', cascade='all')
        )

    @declared_attr
    def temp_blueprint(cls):
        return one_to_many_relationship(
            cls, Blueprint, cls._temp_blueprint_fk,
            backref=db.backref('temp_of_plugins_update', cascade=False),
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
        return one_to_many_relationship(
            cls, Blueprint, cls._old_blueprint_fk,
            backref=db.backref('update_from', cascade=False),
            cascade=False)

    @declared_attr
    def new_blueprint(cls):
        return one_to_many_relationship(
            cls, Blueprint, cls._new_blueprint_fk,
            backref=db.backref('update_to', cascade=False),
            cascade=False)

    deployment_id = association_proxy('deployment', 'id')
    execution_id = association_proxy('execution', 'id')
    old_blueprint_id = association_proxy('old_blueprint', 'id')
    new_blueprint_id = association_proxy('new_blueprint', 'id')

    @declared_attr
    def recursive_dependencies(cls):
        return None

    @declared_attr
    def schedules_to_create(cls):
        return None

    @declared_attr
    def schedules_to_delete(cls):
        return None

    @classproperty
    def response_fields(cls):
        fields = super(DeploymentUpdate, cls).response_fields
        fields['steps'] = flask_fields.List(
            flask_fields.Nested(DeploymentUpdateStep.response_fields)
        )
        dependency_fields = {
            'deployment': flask_fields.String,
            'dependency_type': flask_fields.String,
            'dependent_node': flask_fields.String,
            'tenant': flask_fields.String
        }
        created_scheduled_fields = {
            'id': flask_fields.String,
            'workflow': flask_fields.String,
            'since': flask_fields.String,
            'until': flask_fields.String,
            'count': flask_fields.String,
            'recurring': flask_fields.String,
            'weekdays': flask_fields.List(flask_fields.String)
        }
        fields['recursive_dependencies'] = flask_fields.List(
            flask_fields.Nested(dependency_fields))
        fields['schedules_to_create'] = flask_fields.List(
            flask_fields.Nested(created_scheduled_fields))
        fields['schedules_to_delete'] = flask_fields.List(flask_fields.String)
        return fields

    def to_response(self, **kwargs):
        dep_update_dict = super(DeploymentUpdate, self).to_response()
        # Taking care of the fact the DeploymentSteps are objects
        dep_update_dict['steps'] = [step.to_dict() for step in self.steps]
        dep_update_dict['recursive_dependencies'] = self.recursive_dependencies
        dep_update_dict['schedules_to_create'] = self.schedules_to_create
        dep_update_dict['schedules_to_delete'] = self.schedules_to_delete
        return dep_update_dict

    def set_deployment(self, deployment):
        self._set_parent(deployment)
        self.deployment = deployment

    def set_recursive_dependencies(self, recursive_dependencies):
        self.recursive_dependencies = recursive_dependencies


class DeploymentUpdateStep(SQLResourceBase):
    __tablename__ = 'deployment_update_steps'

    action = db.Column(db.Enum(*ACTION_TYPES, name='action_type'))
    entity_id = db.Column(db.Text, nullable=False)
    entity_type = db.Column(db.Enum(*ENTITY_TYPES, name='entity_type'))
    topology_order = db.Column(db.Integer, nullable=False)

    _deployment_update_fk = foreign_key(DeploymentUpdate._storage_id)

    @declared_attr
    def deployment_update(cls):
        return one_to_many_relationship(
            cls, DeploymentUpdate, cls._deployment_update_fk,
            backref=db.backref('steps', cascade='all'))

    deployment_update_id = association_proxy('deployment_update', 'id')

    def set_deployment_update(self, deployment_update):
        self._set_parent(deployment_update)
        self.deployment_update = deployment_update

    def __lt__(self, other):
        """Is this step considered "smaller" than the other step?

        This is used for sorting the steps, ie. steps that are smaller
        come earlier, and will be executed first.
        """
        if self.action != other.action:
            # the order is 'remove' < 'add' < 'modify'
            actions = ['remove', 'add', 'modify']
            return actions.index(self.action) < actions.index(other.action)
        if self.action == 'add':
            if self.entity_type == NODE:
                if other.entity_type == RELATIONSHIP:
                    # add node before adding relationships
                    return True
                if other.entity_type == NODE:
                    # higher topology order before lower topology order
                    return self.topology_order > other.topology_order
        if self.action == 'remove':
            # remove relationships before removing nodes
            if self.entity_type == RELATIONSHIP and other.entity_type == NODE:
                return True
        return False


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
        return one_to_many_relationship(
            cls, Deployment, cls._deployment_fk,
            backref=db.backref('modifications', cascade='all'))

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
    _source_deployment = foreign_key(Deployment._storage_id, nullable=True)
    _target_deployment = foreign_key(Deployment._storage_id,
                                     nullable=True,
                                     ondelete='SET NULL')
    target_deployment_func = db.Column(JSONString, nullable=True)
    external_source = db.Column(JSONString, nullable=True)
    external_target = db.Column(JSONString, nullable=True)

    @declared_attr
    def source_deployment(cls):
        return one_to_many_relationship(
            cls,
            Deployment,
            cls._source_deployment,
            backref=db.backref('source_of_dependency_in', cascade='all')
        )

    @declared_attr
    def target_deployment(cls):
        return one_to_many_relationship(
            cls,
            Deployment,
            cls._target_deployment,
            backref=db.backref('target_of_dependency_in'),
            cascade='save-update, merge, refresh-expire, expunge')

    source_deployment_id = association_proxy('source_deployment', 'id')
    target_deployment_id = association_proxy('target_deployment', 'id')
# endregion

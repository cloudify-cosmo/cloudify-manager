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

import hashlib
import typing
import uuid

from os import path
from datetime import datetime

from flask_restful import fields as flask_fields

from sqlalchemy import case
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import func, select, table, column, exists
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import validates, aliased
from sqlalchemy.sql.schema import CheckConstraint

from cloudify.constants import MGMTWORKER_QUEUE
from cloudify.models_states import (AgentState,
                                    SnapshotState,
                                    ExecutionState,
                                    DeploymentModificationState,
                                    DeploymentState)
from dsl_parser.constants import WORKFLOW_PLUGINS_TO_INSTALL
from dsl_parser.constraints import extract_constraints, validate_input_value
from dsl_parser import exceptions as dsl_exceptions

from manager_rest import config, manager_exceptions
from manager_rest.rest.responses import Workflow, Label
from manager_rest.utils import (get_rrule,
                                classproperty,
                                files_in_folder)
from manager_rest.deployment_update.constants import ACTION_TYPES, ENTITY_TYPES
from manager_rest.constants import (FILE_SERVER_PLUGINS_FOLDER,
                                    FILE_SERVER_RESOURCES_FOLDER,
                                    AUDIT_OPERATIONS)

from .models_base import (
    db,
    JSONString,
    UTCDateTime,
)
from .management_models import User, Manager
from .resource_models_base import SQLResourceBase, SQLModelBase
from .relationships import (
    foreign_key,
    one_to_many_relationship,
    many_to_many_relationship
)


if typing.TYPE_CHECKING:
    from manager_rest.resource_manager import ResourceManager
    from manager_rest.storage.storage_manager import SQLStorageManager


RELATIONSHIP = 'relationship'
NODE = 'node'


class CreatedAtMixin(object):
    created_at = db.Column(UTCDateTime, nullable=False, index=True,
                           default=lambda: datetime.utcnow())

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
        return ['created_by', 'state']

    def to_response(self, include=None, **kwargs):
        include = include or self.response_fields
        blueprint_dict = super(Blueprint, self).to_response(include, **kwargs)
        if 'labels' in include:
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

    def to_response(self, include=None, get_data=False, **kwargs):
        include = include or self.response_fields
        plugin_dict = super(Plugin, self).to_response(include, **kwargs)
        if not get_data:
            plugin_dict['file_server_path'] = ''
        if 'installation_state' in plugin_dict \
                and 'installation_state' in include:
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
        if not hasattr(cls, '_cached_site_fields'):
            fields = super(Site, cls).response_fields
            fields.pop('id')
            cls._cached_site_fields = fields
        return cls._cached_site_fields

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
        db.Index(
            'deployments__latest_execution_fk_idx',
            '_latest_execution_fk',
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
    sub_services_status = db.Column(db.Enum(
            DeploymentState.GOOD,
            DeploymentState.IN_PROGRESS,
            DeploymentState.REQUIRE_ATTENTION,
            name='deployment_status'
        ))
    sub_environments_status = db.Column(db.Enum(
            DeploymentState.GOOD,
            DeploymentState.IN_PROGRESS,
            DeploymentState.REQUIRE_ATTENTION,
            name='deployment_status'
        ))
    sub_services_count = db.Column(
        db.Integer, nullable=False, server_default='0')
    sub_environments_count = db.Column(
        db.Integer, nullable=False, server_default='0')
    display_name = db.Column(
        db.Text, nullable=False, index=True,
        default=lambda ctx: ctx.get_current_parameters().get('id')
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
                                       use_alter=True,
                                       unique=True)

    deployment_group_id = association_proxy('deployment_groups', 'id')
    latest_execution_finished_operations = association_proxy(
        'latest_execution', 'finished_operations')
    latest_execution_total_operations = association_proxy(
        'latest_execution', 'total_operations')

    @classproperty
    def autoload_relationships(cls):
        return [
            cls.create_execution,
            cls.latest_execution,
            cls.deployment_groups,
            cls.labels,
            cls.schedules,
        ]

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
    latest_execution_status = association_proxy('latest_execution', 'status')

    @classproperty
    def response_fields(cls):
        if not hasattr(cls, '_cached_deployment_fields'):
            fields = super(Deployment, cls).response_fields
            fields['labels'] = flask_fields.List(
                flask_fields.Nested(Label.resource_fields))
            fields.pop('deployment_group_id', None)
            fields['workflows'] = flask_fields.List(
                flask_fields.Nested(Workflow.resource_fields)
            )
            fields['schedules'] = flask_fields.List(
                flask_fields.Nested(ExecutionSchedule.resource_fields))
            fields['deployment_groups'] = \
                flask_fields.List(flask_fields.String)
            fields['latest_execution_status'] = flask_fields.String()
            fields['latest_execution_total_operations'] = \
                flask_fields.Integer()
            fields['latest_execution_finished_operations'] = \
                flask_fields.Integer()
            fields['has_sub_deployments'] = \
                flask_fields.Boolean()
            cls._cached_deployment_fields = fields
        return cls._cached_deployment_fields

    @classproperty
    def allowed_filter_attrs(cls):
        return ['blueprint_id', 'created_by', 'site_name', 'schedules']

    def to_response(self, include=None, **kwargs):
        include = include or self.response_fields
        dep_dict = super(Deployment, self).to_response(
            include=include, **kwargs)
        if 'workflows' in include:
            dep_dict['workflows'] = self._list_workflows(self.workflows)
        if 'labels' in include:
            dep_dict['labels'] = self.list_labels(self.labels)
        if 'deployment_groups' in include:
            dep_dict['deployment_groups'] = \
                [g.id for g in self.deployment_groups]
        if 'latest_execution_status' in include:
            dep_dict['latest_execution_status'] = \
                DeploymentState.EXECUTION_STATES_SUMMARY.get(
                    self.latest_execution_status)
        if 'installation_status' in include:
            if not dep_dict.get('installation_status'):
                dep_dict['installation_status'] = DeploymentState.INACTIVE
        if 'latest_execution_total_operations' in include:
            dep_dict['latest_execution_total_operations'] = \
                self.latest_execution_total_operations
        if 'latest_execution_finished_operations' in include:
            dep_dict['latest_execution_finished_operations'] = \
                self.latest_execution_finished_operations
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

    def compare_between_statuses(
            self,
            first_status,
            second_status
    ):
        """
        Compare between two deployment statuses so that we can tell which
        one is worst than others. If first_status > second_status then
        return the first status otherwise return the second_status
        :param first_status: The first deployment status
        :rtype str
        :param second_status: The second deployment status
        :rtype str
        :return: Return the end result status
        :rtype str
        """
        class _DeploymentStatus(object):
            def __init__(self, status):
                self.status = status

            def __gt__(self, other):
                if not self.status:
                    return False
                elif self.status and not other.status:
                    return True
                elif (self.status == DeploymentState.REQUIRE_ATTENTION and
                      other.status in [
                          DeploymentState.GOOD,
                          DeploymentState.IN_PROGRESS
                      ]):
                    return True
                elif (
                        self.status == DeploymentState.IN_PROGRESS
                        and other.status == DeploymentState.GOOD):
                    return True
                return False

        _source = _DeploymentStatus(first_status)
        _target = _DeploymentStatus(second_status)
        return _source.status if _source > _target else _target.status

    def evaluate_sub_deployments_statuses(self):
        """
        Evaluate the deployment statuses per deployment using the following
        three statuses
        1. sub_environments_status
        2. sub_services_status
        3. deployment_status
        This is useful and prerequisite before propagate the source
        deployments statuses to the target
        :return: Tuple of end result of `sub_environments_status`
         & `sub_services_status`
        :rtype Tuple
        """
        _sub_environments_status = self.sub_environments_status
        _sub_services_status = self.sub_services_status
        if self.is_environment:
            _sub_environments_status = \
                self.compare_between_statuses(
                    self.sub_environments_status,
                    self.deployment_status
                )

        else:
            _sub_services_status = \
                self.compare_between_statuses(
                    self.sub_services_status,
                    self.deployment_status
                )
        return _sub_services_status, _sub_environments_status

    def evaluate_deployment_status(self, exclude_sub_deployments=False):
        """
        Evaluate the overall deployment status based on installation status
        and latest execution object
        :return: deployment_status: Overall deployment status
        """
        latest_status = DeploymentState.EXECUTION_STATES_SUMMARY.get(
            self.latest_execution_status)
        if latest_status == DeploymentState.IN_PROGRESS:
            deployment_status = DeploymentState.IN_PROGRESS
        elif latest_status == DeploymentState.FAILED \
                or self.installation_status == DeploymentState.INACTIVE:
            deployment_status = DeploymentState.REQUIRE_ATTENTION
        else:
            deployment_status = DeploymentState.GOOD

        has_sub_sts = self.sub_services_status or self.sub_environments_status
        if not has_sub_sts or exclude_sub_deployments:
            return deployment_status

        # Check whether or not deployment has services or environments
        # attached to it, so that we can consider that while evaluating the
        # deployment status
        if self.sub_services_status:
            deployment_status = \
                self.compare_between_statuses(
                    self.sub_services_status,
                    deployment_status
                )
        if self.sub_environments_status:
            deployment_status = \
                self.compare_between_statuses(
                    self.sub_environments_status,
                    deployment_status
                )
        return deployment_status

    @property
    def is_environment(self):
        target_key = 'csys-obj-type'
        target_value = 'environment'
        for label in self.labels:
            if label.key == target_key and label.value == target_value:
                return True
        return False

    @property
    def deployment_parents(self):
        parents = []
        for label in self.labels:
            if label.key == 'csys-obj-parent' and label.value:
                parents.append(label.value)
        return parents

    def make_create_environment_execution(self, inputs=None, **params):
        if inputs is not None and self.blueprint and self.blueprint.plan:
            self._validate_inputs(inputs)
        self.create_execution = Execution(
            workflow_id='create_deployment_environment',
            deployment=self,
            status=ExecutionState.PENDING,
            parameters={'inputs': inputs, **params},
        )
        self.latest_execution = self.create_execution
        return self.create_execution

    def _validate_inputs(self, inputs):
        blueprint_inputs = self.blueprint.plan.get('inputs', {})
        allowed_inputs = set(blueprint_inputs)
        required_inputs = {
            name for name, input_spec in blueprint_inputs.items()
            if 'default' not in input_spec
        }
        provided_inputs = set(inputs)
        missing_inputs = required_inputs - provided_inputs
        undeclared_inputs = provided_inputs - allowed_inputs
        if missing_inputs:
            raise manager_exceptions.MissingRequiredDeploymentInputError(
                f'missing inputs: { ", ".join(missing_inputs) }'
            )
        if undeclared_inputs:
            raise manager_exceptions.UnknownDeploymentInputError(
                f'Cannot create deployment - unknown inputs: '
                f'{ ", ".join(undeclared_inputs) }'
            )

    def make_delete_environment_execution(self, delete_logs=True):
        return Execution(
            workflow_id='delete_deployment_environment',
            deployment=self,
            status=ExecutionState.PENDING,
            parameters={'delete_logs': delete_logs},
        )

    @hybrid_property
    def environment_type(self):
        for label in self.labels:
            if label.key == 'csys-env-type':
                return label.value
        return ''

    @environment_type.expression
    def environment_type(cls):
        labels_table = aliased(DeploymentLabel.__table__)
        env_type_stmt = (
            select([labels_table.c.value]).
            where(db.and_(
                    labels_table.c.key == 'csys-env-type',
                    labels_table.c._labeled_model_fk == cls._storage_id)).
            distinct().
            limit(1)
        )

        return case([(exists(env_type_stmt),
                      env_type_stmt.label('environment_type'))],
                    else_='')

    @hybrid_property
    def has_sub_deployments(self):
        return self.sub_services_count or self.sub_environments_count

    @has_sub_deployments.expression
    def has_sub_deployments(self):
        return (self.sub_services_count + self.sub_environments_count) > 0


class DeploymentGroup(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'deployment_groups'
    description = db.Column(db.Text)
    default_inputs = db.Column(JSONString)
    creation_counter = db.Column(db.Integer, default=0, nullable=False)
    _default_blueprint_fk = foreign_key(
        Blueprint._storage_id,
        ondelete='SET NULL',
        nullable=True)

    deployment_ids = association_proxy('deployments', 'id')
    default_blueprint_id = association_proxy('default_blueprint', 'id')

    @declared_attr
    def default_blueprint(cls):
        return one_to_many_relationship(
            cls, Blueprint, cls._default_blueprint_fk)

    @declared_attr
    def deployments(cls):
        return many_to_many_relationship(cls, Deployment, unique=True)

    @classproperty
    def response_fields(cls):
        fields = super(DeploymentGroup, cls).response_fields
        fields['deployment_ids'] = flask_fields.List(
            flask_fields.String()
        )
        fields['labels'] = flask_fields.List(
            flask_fields.Nested(Label.resource_fields))
        fields['default_blueprint_id'] = flask_fields.String()
        return fields

    def to_response(self, include=None, get_data=False, **kwargs):
        include = include or self.response_fields
        response = super(DeploymentGroup, self).to_response(include, **kwargs)
        if get_data or 'labels' in include:
            response['labels'] = self.list_labels(self.labels)
        return response


class LabelBase(CreatedAtMixin, SQLModelBase):
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


class DeploymentLabel(LabelBase):
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


class BlueprintLabel(LabelBase):
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


class DeploymentGroupLabel(LabelBase):
    __tablename__ = 'deployment_groups_labels'
    __table_args__ = (
        db.UniqueConstraint(
            'key', 'value', '_labeled_model_fk'),
    )
    labeled_model = DeploymentGroup

    _labeled_model_fk = foreign_key(DeploymentGroup._storage_id)

    @declared_attr
    def deployment_group(cls):
        return db.relationship(
            DeploymentGroup, lazy='joined',
            backref=db.backref('labels', cascade='all, delete-orphan'))


class FilterBase(CreatedAtMixin, SQLResourceBase):
    __abstract__ = True
    _extra_fields = {'labels_filter_rules': flask_fields.Raw,
                     'attrs_filter_rules': flask_fields.Raw}

    value = db.Column(JSONString, nullable=True)
    updated_at = db.Column(UTCDateTime)
    is_system_filter = db.Column(db.Boolean,
                                 nullable=False,
                                 index=True,
                                 default=False)

    @property
    def labels_filter_rules(self):
        return [filter_rule for filter_rule in self.value
                if filter_rule['type'] == 'label']

    @property
    def attrs_filter_rules(self):
        return [filter_rule for filter_rule in self.value
                if filter_rule['type'] == 'attribute']


class DeploymentsFilter(FilterBase):
    __tablename__ = 'deployments_filters'
    __table_args__ = (
        db.Index(
            'deployments_filters_id__tenant_id_idx',
            'id', '_tenant_id',
            unique=True
        ),
    )


class BlueprintsFilter(FilterBase):
    __tablename__ = 'blueprints_filters'
    __table_args__ = (
        db.Index(
            'blueprints_filters_id__tenant_id_idx',
            'id', '_tenant_id',
            unique=True
        ),
    )


class Execution(CreatedAtMixin, SQLResourceBase):
    def __init__(self, **kwargs):
        # allow-custom must be set before other attributes, necessarily
        # before parameters
        self.allow_custom_parameters = kwargs.pop(
            'allow_custom_parameters', False)
        super().__init__(**kwargs)

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
    id = db.Column(db.Text, index=True, default=lambda: str(uuid.uuid4()))
    ended_at = db.Column(UTCDateTime, nullable=True, index=True)
    error = db.Column(db.Text)
    is_system_workflow = db.Column(db.Boolean, nullable=False, index=True,
                                   default=False)
    parameters = db.Column(db.PickleType(protocol=2))
    status = db.Column(
        db.Enum(*ExecutionState.STATES, name='execution_status')
    )
    workflow_id = db.Column(db.Text, nullable=False)
    started_at = db.Column(UTCDateTime, nullable=True)
    scheduled_for = db.Column(UTCDateTime, nullable=True)
    is_dry_run = db.Column(db.Boolean, nullable=False, default=False)
    token = db.Column(db.String(100), nullable=True, index=True)
    resume = db.Column(db.Boolean, nullable=False, server_default='false')

    _deployment_fk = foreign_key(Deployment._storage_id, nullable=True)

    total_operations = db.Column(db.Integer, nullable=True)
    finished_operations = db.Column(db.Integer, nullable=True)
    allow_custom_parameters = db.Column(db.Boolean, nullable=False,
                                        server_default='false')
    execution_group_id = association_proxy('execution_groups', 'id')
    deployment_display_name = association_proxy('deployment', 'display_name')

    @classproperty
    def autoload_relationships(cls):
        return [
            cls.deployment,
        ]

    def __repr__(self):
        return (
            f'<Execution id=`{self.id}` tenant=`{self.tenant_name}` '
            f'status=`{self.status}` workflow_id=`{self.workflow_id}`>'
        )

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

    @classproperty
    def resource_fields(cls):
        fields = super(Execution, cls).resource_fields
        fields.pop('token')
        fields['deployment_display_name'] = flask_fields.String()
        return fields

    @classproperty
    def response_fields(cls):
        if not hasattr(cls, '_cached_execution_fields'):
            fields = super(Execution, cls).response_fields
            fields.pop('execution_group_id')
            cls._cached_execution_fields = fields
        return cls._cached_execution_fields

    @validates('deployment')
    def _set_deployment(self, key, deployment):
        self._set_parent(deployment)
        if self.blueprint_id is None:
            self.blueprint_id = deployment.blueprint_id
        if self.parameters is not None and self.workflow_id is not None:
            self.merge_workflow_parameters(
                self.parameters, deployment, self.workflow_id)
        return deployment

    @validates('workflow_id')
    def _validate_workflow_id(self, key, workflow_id):
        if self.parameters is not None and self.deployment is not None:
            self.merge_workflow_parameters(
                self.parameters, self.deployment, workflow_id)
        return workflow_id

    @validates('parameters')
    def _validate_parameters(self, key, parameters):
        parameters = parameters or {}
        if self.workflow_id is not None and self.deployment is not None:
            self.merge_workflow_parameters(
                parameters, self.deployment, self.workflow_id)
        return parameters

    def _system_workflow_task_name(self, wf_id):
        return {
            'create_snapshot': 'cloudify_system_workflows.snapshot.create',
            'restore_snapshot': 'cloudify_system_workflows.snapshot.restore',
            'uninstall_plugin': 'cloudify_system_workflows.plugins.uninstall',
            'create_deployment_environment':
                'cloudify_system_workflows.deployment_environment.create',
            'delete_deployment_environment':
                'cloudify_system_workflows.deployment_environment.delete',
            'update_plugin': 'cloudify_system_workflows.plugins.update',
            'upload_blueprint': 'cloudify_system_workflows.blueprint.upload',
            'csys_update_deployment':
                'cloudify_system_workflows.deployment_environment.'
                'update_deployment',
            'csys_new_deployment_update':
                'cloudify_system_workflows.deployment_update.workflow.'
                'update_deployment',
        }.get(wf_id)

    def get_workflow(self, deployment=None, workflow_id=None):
        deployment = deployment or self.deployment
        workflow_id = workflow_id or self.workflow_id

        if deployment and deployment.workflows\
                and workflow_id in deployment.workflows:
            return deployment.workflows[workflow_id]
        system_task_name = self._system_workflow_task_name(workflow_id)
        if system_task_name:
            self.allow_custom_parameters = True
            return {'operation': system_task_name}
        if deployment:
            raise manager_exceptions.NonexistentWorkflowError(
                f'Workflow {workflow_id} does not exist in the '
                f'deployment {deployment.id}')
        else:
            raise manager_exceptions.NonexistentWorkflowError(
                f'Builtin workflow {workflow_id} does not exist')

    def merge_workflow_parameters(self, parameters, deployment, workflow_id):
        if not deployment or not deployment.workflows:
            return
        workflow = self.get_workflow(deployment, workflow_id)
        workflow_parameters = workflow.get('parameters', {})
        custom_parameters = parameters.keys() - workflow_parameters.keys()
        if not self.allow_custom_parameters and custom_parameters:
            raise manager_exceptions.IllegalExecutionParametersError(
                f'Workflow "{workflow_id}" does not have the following '
                f'parameters declared: { ",".join(custom_parameters) }. '
                f'Remove these parameters or use the flag for allowing '
                f'custom parameters') from None

        wrong_types = {}
        for name, param in workflow_parameters.items():
            declared_type = param.get('type')
            if declared_type is None or name not in parameters:
                continue
            try:
                parameters[name] = self._convert_param_type(
                        parameters[name], declared_type)
            except ValueError:
                wrong_types[name] = declared_type
        if wrong_types:
            raise manager_exceptions.IllegalExecutionParametersError('\n'.join(
                f'Parameter "{n}" must be of type {t}'
                for n, t in wrong_types.items())
            )

        for name, param in workflow_parameters.items():
            if 'default' in param:
                parameters.setdefault(name, param['default'])

        constraint_violations = {}
        for name, param in workflow_parameters.items():
            constraints = extract_constraints(param)
            if not constraints or name not in parameters:
                continue
            try:
                validate_input_value(name, constraints, parameters[name])
            except (dsl_exceptions.DSLParsingException,
                    dsl_exceptions.ConstraintException) as ex:
                constraint_violations[name] = ex
        if constraint_violations:
            raise manager_exceptions.IllegalExecutionParametersError('\n'.join(
                f'Parameter "{n}" does not meet its constraints: {e}'
                for n, e in constraint_violations.items()
            ))

        missing_parameters = workflow_parameters.keys() - parameters.keys()
        if missing_parameters:
            raise manager_exceptions.IllegalExecutionParametersError(
                f'Workflow "{workflow_id}" must be provided with the following'
                f' parameters to execute: { ",".join(missing_parameters) }'
            ) from None

    def _convert_param_type(self, param, target_type):
        if target_type == 'integer':
            return int(param)
        elif target_type == 'boolean':
            if isinstance(param, bool):
                return param
            elif param.lower() == 'true':
                return True
            elif param.lower() == 'false':
                return False
            else:
                raise ValueError(param)
        elif target_type == 'float':
            return float(param)
        elif target_type == 'string':
            if isinstance(param, str):
                return param
            else:
                raise ValueError(param)
        else:
            return param

    def render_message(self, wait_after_fail=600, bypass_maintenance=None):
        self.ensure_defaults()
        workflow = self.get_workflow()
        session = db.session.object_session(self)

        token = uuid.uuid4().hex
        context = {
            'type': 'workflow',
            'task_id': self.id,
            'execution_id': self.id,
            'task_name': workflow['operation'],
            'workflow_id': self.workflow_id,
            'dry_run': self.is_dry_run,
            'is_system_workflow': self.is_system_workflow,
            'execution_creator_username': self.creator.username,
            'task_target': MGMTWORKER_QUEUE,
            'tenant': {'name': self.tenant.name},
            'resume': self.resume,
            'wait_after_fail': wait_after_fail,
            'bypass_maintenance': bypass_maintenance,
            'execution_token': token,
            'rest_token': self.creator.get_auth_token(),
            'rest_host': [
                mgr.private_ip for mgr in session.query(Manager).all()
            ],
        }
        if self.deployment is not None:
            context['deployment_id'] = self.deployment.id
            context['blueprint_id'] = self.blueprint_id
            context['runtime_only_evaluation'] = \
                self.deployment.runtime_only_evaluation
        plugin_name = workflow.get('plugin')
        if plugin_name:
            blueprint = self.deployment.blueprint
            workflow_plugins = blueprint.plan[WORKFLOW_PLUGINS_TO_INSTALL]
            plugins = [p for p in workflow_plugins if p['name'] == plugin_name]
            if plugins:
                plugin = plugins[0]
                context['plugin'] = {
                    'name': plugin_name,
                    'package_name': plugin.get('package_name'),
                    'package_version': plugin.get('package_version'),
                    'visibility': plugin.get('visibility'),
                    'tenant_name': plugin.get('tenant_name'),
                    'source': plugin.get('source')
                }
                managed_plugin = (
                    session.query(Plugin)
                    .tenant(self.tenant)
                    .filter_by(
                        package_name=plugin.get('package_name'),
                        package_version=plugin.get('package_version'),
                    )
                    .first()
                )
                if managed_plugin:
                    context['plugin'].update(
                        visibility=managed_plugin.visibility,
                        tenant_name=managed_plugin.tenant_name
                    )
        self.merge_workflow_parameters(
            self.parameters,
            self.deployment,
            self.workflow_id
        )
        parameters = self.parameters.copy()
        parameters['__cloudify_context'] = context

        self.token = hashlib.sha256(token.encode('ascii')).hexdigest()
        session.add(self)
        return {
            'cloudify_task': {'kwargs': parameters},
            'id': self.id,
            'execution_creator': self.creator.id
        }


class ExecutionGroup(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'execution_groups'
    _deployment_group_fk = foreign_key(
        DeploymentGroup._storage_id, nullable=True)
    workflow_id = db.Column(db.Text, nullable=False)
    concurrency = db.Column(db.Integer, server_default='5', nullable=False)
    _success_group_fk = foreign_key(DeploymentGroup._storage_id, nullable=True,
                                    ondelete='SET NULL')
    _failed_group_fk = foreign_key(DeploymentGroup._storage_id, nullable=True,
                                   ondelete='SET NULL')
    execution_ids = association_proxy('executions', 'id')

    @declared_attr
    def deployment_group(cls):
        return one_to_many_relationship(
            cls, DeploymentGroup, cls._deployment_group_fk)

    @declared_attr
    def success_group(cls):
        return one_to_many_relationship(
            cls, DeploymentGroup, cls._success_group_fk,
            backref='success_source_execution_group')

    @declared_attr
    def failed_group(cls):
        return one_to_many_relationship(
            cls, DeploymentGroup, cls._failed_group_fk,
            backref='failed_source_execution_group')

    deployment_group_id = association_proxy('deployment_group', 'id')

    @declared_attr
    def executions(cls):
        return many_to_many_relationship(
            cls, Execution,
            ondelete='CASCADE'
        )

    def currently_running_executions(self):
        return [
            exc for exc in self.executions
            if exc.status in ExecutionState.IN_PROGRESS_STATES
        ]

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
            - queued, if all executions are either queued, pending or scheduled
            - started, if some executions are already not pending, and not
                all are finished yet
            - failed, if all executions are finished, and some have failed
            - terminated, if all are finished, and none have failed (but
                some might have been cancelled)
        """
        states = {e.status for e in self.executions}

        if all(s == ExecutionState.PENDING for s in states):
            return ExecutionState.PENDING

        QUEUED_STATES = (ExecutionState.WAITING_STATES +
                         [ExecutionState.PENDING])
        if all(s in QUEUED_STATES for s in states):
            return ExecutionState.QUEUED

        if all(s in ExecutionState.END_STATES for s in states):
            if ExecutionState.FAILED in states:
                return ExecutionState.FAILED
            return ExecutionState.TERMINATED

        return ExecutionState.STARTED

    def to_response(self, include=None, get_data=False, **kwargs):
        include = include or self.response_fields
        if not get_data:
            skip_fields = ['execution_ids', 'status']
        else:
            skip_fields = []
        return {
            f: getattr(self, f)
            for f in self.response_fields
            if f not in skip_fields and f in include
        }

    def start_executions(self,
                         sm: 'SQLStorageManager',
                         rm: 'ResourceManager',
                         force=False):
        """Start the executions belonging to this group.

        This will only actually run executions up to the concurrency limit,
        and queue the rest.
        """
        executions = [
            exc for exc in self.executions
            if exc.status == ExecutionState.PENDING
        ]
        for execution in executions[self.concurrency:]:
            execution.status = ExecutionState.QUEUED
            sm.update(execution, modified_attrs=('status', ))

        return rm.prepare_executions(
            executions[:self.concurrency], force=force, queue=True)


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
        return one_to_many_relationship(
            cls, Deployment, cls._deployment_fk,
            backref=db.backref('schedules', cascade='all, delete-orphan'))

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
        CheckConstraint(
            '(_execution_fk IS NOT NULL) != (_execution_group_fk IS NOT NULL)',
            name='events__one_fk_not_null'
        ),
    )
    is_id_unique = False

    id = None  # this is just to override the parent class attribute
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

    _execution_fk = foreign_key(Execution._storage_id, nullable=True)
    _execution_group_fk = foreign_key(ExecutionGroup._storage_id,
                                      nullable=True)

    @classmethod
    def default_sort_column(cls):
        return cls.reported_timestamp

    @declared_attr
    def execution(cls):
        return one_to_many_relationship(cls, Execution, cls._execution_fk)

    execution_id = association_proxy('execution', 'id')

    @declared_attr
    def execution_group(cls):
        return one_to_many_relationship(cls, ExecutionGroup,
                                        cls._execution_group_fk)

    execution_group_id = association_proxy('execution_group', 'id')

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
        CheckConstraint(
            '(_execution_fk IS NOT NULL) != (_execution_group_fk IS NOT NULL)',
            name='logs__one_fk_not_null'
        ),
    )
    is_id_unique = False

    id = None  # this is just to override the parent class attribute
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

    _execution_fk = foreign_key(Execution._storage_id, nullable=True)
    _execution_group_fk = foreign_key(ExecutionGroup._storage_id,
                                      nullable=True)

    @classmethod
    def default_sort_column(cls):
        return cls.reported_timestamp

    @declared_attr
    def execution(cls):
        return one_to_many_relationship(cls, Execution, cls._execution_fk)

    execution_id = association_proxy('execution', 'id')

    @declared_attr
    def execution_group(cls):
        return one_to_many_relationship(cls, ExecutionGroup,
                                        cls._execution_group_fk)

    execution_group_id = association_proxy('execution_group', 'id')

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

    @declared_attr
    def labels_to_create(cls):
        return None

    @classproperty
    def response_fields(cls):
        if not hasattr(cls, '_cached_depupdate_fields'):
            fields = super(DeploymentUpdate, cls).response_fields
            fields.pop('deployment_update_deployment')
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
                'recurrence': flask_fields.String,
                'weekdays': flask_fields.List(flask_fields.String)
            }
            fields['recursive_dependencies'] = flask_fields.List(
                flask_fields.Nested(dependency_fields))
            fields['schedules_to_create'] = flask_fields.List(
                flask_fields.Nested(created_scheduled_fields))
            fields['schedules_to_delete'] = \
                flask_fields.List(flask_fields.String)
            fields['labels_to_create'] = flask_fields.List(flask_fields.Raw)
            cls._cached_depupdate_fields = fields
        return cls._cached_depupdate_fields

    def to_response(self, include=None, **kwargs):
        include = include or self.response_fields
        dep_update_dict = super(DeploymentUpdate, self).to_response(
            include, **kwargs)
        if 'steps' in include:
            dep_update_dict['steps'] = [step.to_dict() for step in self.steps]
        if 'recursive_dependencies' in include:
            dep_update_dict['recursive_dependencies'] = \
                self.recursive_dependencies
        if 'schedules_to_create' in include:
            dep_update_dict['schedules_to_create'] = self.schedules_to_create
        if 'schedules_to_delete' in include:
            dep_update_dict['schedules_to_delete'] = self.schedules_to_delete
        if 'labels_to_create' in include:
            dep_update_dict['labels_to_create'] = self.labels_to_create
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
    deployment_display_name = association_proxy('deployment', 'display_name')

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
        return one_to_many_relationship(
            cls, Node, cls._node_fk,
            backref=db.backref(
                'instances', lazy='subquery', cascade='all, delete')
        )

    node_id = association_proxy('node', 'id')
    deployment_id = association_proxy('node', 'deployment_id')

    def set_node(self, node):
        self._set_parent(node)
        self.node = node

    @classproperty
    def allowed_filter_attrs(cls):
        return ['id']


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

    def to_response(self, include=None, **kwargs):
        include = include or self.response_fields
        agent_dict = super(Agent, self).to_response(include, **kwargs)
        agent_dict.pop('rabbitmq_username', None)
        agent_dict.pop('rabbitmq_password', None)
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
    is_id_unique = False

    id = db.Column(db.Text, index=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.Text, index=True)
    created_at = db.Column(UTCDateTime, nullable=False, index=True)

    _execution_fk = foreign_key(Execution._storage_id)

    @declared_attr
    def execution(cls):
        return one_to_many_relationship(cls, Execution, cls._execution_fk)

    execution_id = association_proxy('execution', 'id')


class Operation(CreatedAtMixin, SQLResourceBase):
    __tablename__ = 'operations'
    is_id_unique = False

    id = db.Column(db.Text, index=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.Text)
    state = db.Column(db.Text, nullable=False)

    dependencies = db.Column(db.ARRAY(db.Text))
    type = db.Column(db.Text)
    parameters = db.Column(JSONString)

    _tasks_graph_fk = foreign_key(TasksGraph._storage_id)

    @declared_attr
    def tasks_graph(cls):
        return one_to_many_relationship(cls, TasksGraph, cls._tasks_graph_fk)

    @property
    def is_nop(self):
        return self.type == 'NOPLocalWorkflowTask'


class BaseDeploymentDependencies(CreatedAtMixin, SQLResourceBase):
    __abstract__ = True
    _source_deployment = None
    _target_deployment = None

    _source_backref_name = None
    _target_backref_name = None

    _source_cascade = 'all'
    _target_cascade = 'all'

    @declared_attr
    def source_deployment(cls):
        return one_to_many_relationship(
            cls,
            Deployment,
            cls._source_deployment,
            backref=db.backref(
                cls._source_backref_name,
                cascade=cls._source_cascade
            )
        )

    @declared_attr
    def target_deployment(cls):
        return one_to_many_relationship(
            cls,
            Deployment,
            cls._target_deployment,
            backref=db.backref(
                cls._target_backref_name,
                cascade=cls._target_cascade
            )
        )

    source_deployment_id = association_proxy('source_deployment', 'id')
    target_deployment_id = association_proxy('target_deployment', 'id')


class InterDeploymentDependencies(BaseDeploymentDependencies):
    __tablename__ = 'inter_deployment_dependencies'

    _source_backref_name = 'source_of_dependency_in'
    _target_backref_name = 'target_of_dependency_in'

    _target_cascade = 'save-update, merge, refresh-expire, expunge'

    _source_deployment = foreign_key(Deployment._storage_id, nullable=True)
    _target_deployment = foreign_key(Deployment._storage_id,
                                     nullable=True,
                                     ondelete='SET NULL')

    dependency_creator = db.Column(db.Text, nullable=False)
    target_deployment_func = db.Column(JSONString, nullable=True)
    external_source = db.Column(JSONString, nullable=True)
    external_target = db.Column(JSONString, nullable=True)


class DeploymentLabelsDependencies(BaseDeploymentDependencies):
    __tablename__ = 'deployment_labels_dependencies'
    __table_args__ = (
        db.UniqueConstraint(
            '_source_deployment', '_target_deployment'),
    )

    _source_backref_name = 'source_of_dependency_labels'
    _target_backref_name = 'target_of_dependency_labels'

    _source_deployment = foreign_key(Deployment._storage_id)
    _target_deployment = foreign_key(Deployment._storage_id)


class AuditLog(CreatedAtMixin, SQLModelBase):
    __tablename__ = 'audit_log'
    __table_args__ = (
        db.Index(
            'audit_log_ref_idx',
            'ref_table', 'ref_id',
            unique=False
        ),
    )
    _storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ref_table = db.Column(db.Text, nullable=False, index=True)
    ref_id = db.Column(db.Integer, nullable=False)
    operation = db.Column(db.Enum(*AUDIT_OPERATIONS, name='audit_operation'),
                          nullable=False)
    creator_name = db.Column(db.Text, nullable=True)
    execution_id = db.Column(db.Text, nullable=True)
# endregion

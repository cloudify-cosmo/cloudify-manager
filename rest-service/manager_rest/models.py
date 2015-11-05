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

import json


class SerializableObject(object):

    def to_dict(self):
        # attr_and_values = ((attr, getattr(self, attr)) for attr in dir(self)
        #                    if not attr.startswith("__"))
        # return {attr: value for attr, value in
        #         attr_and_values if not callable(value)}
        return {field: getattr(self, field) for field in self.fields}

    def to_json(self):
        return json.dumps(self.to_dict())


class BlueprintState(SerializableObject):

    fields = {
        'plan', 'id', 'description', 'created_at', 'updated_at',
        'main_file_name'
    }

    def __init__(self, **kwargs):
        self.plan = kwargs['plan']
        self.id = kwargs['id']
        self.description = kwargs['description']
        self.created_at = kwargs['created_at']
        self.updated_at = kwargs['updated_at']
        self.main_file_name = kwargs['main_file_name']


class Snapshot(SerializableObject):

    CREATED = 'created'
    FAILED = 'failed'
    CREATING = 'creating'
    UPLOADED = 'uploaded'

    END_STATES = [CREATED, FAILED, UPLOADED]

    fields = {'id', 'created_at', 'status', 'error'}

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.created_at = kwargs['created_at']
        self.status = kwargs['status']
        self.error = kwargs['error']


class Deployment(SerializableObject):

    fields = {'id', 'created_at', 'updated_at', 'blueprint_id',
              'workflows', 'permalink', 'inputs', 'policy_types',
              'policy_triggers', 'groups', 'outputs'}

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.created_at = kwargs['created_at']
        self.updated_at = kwargs['updated_at']
        self.blueprint_id = kwargs['blueprint_id']
        self.workflows = kwargs['workflows']
        self.inputs = kwargs['inputs']
        self.policy_types = kwargs['policy_types']
        self.policy_triggers = kwargs['policy_triggers']
        self.groups = kwargs['groups']
        self.outputs = kwargs['outputs']
        self.permalink = None  # TODO: implement


class DeploymentModification(SerializableObject):

    STARTED = 'started'
    FINISHED = 'finished'
    ROLLEDBACK = 'rolledback'

    END_STATES = [FINISHED, ROLLEDBACK]

    fields = {'id', 'deployment_id', 'modified_nodes', 'node_instances',
              'status', 'created_at', 'ended_at', 'context'}

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.created_at = kwargs['created_at']
        self.ended_at = kwargs['ended_at']
        self.status = kwargs['status']
        self.deployment_id = kwargs['deployment_id']
        self.modified_nodes = kwargs['modified_nodes']
        self.node_instances = kwargs['node_instances']
        self.context = kwargs['context']


class Execution(SerializableObject):

    TERMINATED = 'terminated'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    PENDING = 'pending'
    STARTED = 'started'
    CANCELLING = 'cancelling'
    FORCE_CANCELLING = 'force_cancelling'

    STATES = [TERMINATED, FAILED, CANCELLED, PENDING, STARTED,
              CANCELLING, FORCE_CANCELLING]
    END_STATES = [TERMINATED, FAILED, CANCELLED]
    ACTIVE_STATES = [state for state in STATES if state not in END_STATES]

    fields = {'id', 'status', 'deployment_id', 'workflow_id', 'blueprint_id',
              'created_at', 'error', 'parameters', 'is_system_workflow'}

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.status = kwargs['status']
        self.deployment_id = kwargs['deployment_id']
        self.workflow_id = kwargs['workflow_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.created_at = kwargs['created_at']
        self.error = kwargs['error']
        self.parameters = kwargs['parameters']
        self.is_system_workflow = kwargs['is_system_workflow']


class DeploymentNode(SerializableObject):
    """
    Represents a node in a deployment.
    """

    fields = {
        'id', 'deployment_id', 'blueprint_id', 'type', 'type_hierarchy',
        'number_of_instances', 'planned_number_of_instances',
        'deploy_number_of_instances', 'host_id', 'properties',
        'operations', 'plugins', 'relationships', 'plugins_to_install'
    }

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.deployment_id = kwargs['deployment_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.type = kwargs['type']
        self.type_hierarchy = kwargs['type_hierarchy']
        self.number_of_instances = kwargs['number_of_instances']
        self.planned_number_of_instances = kwargs[
            'planned_number_of_instances']
        self.deploy_number_of_instances = kwargs['deploy_number_of_instances']
        self.host_id = kwargs['host_id']
        self.properties = kwargs['properties']
        self.operations = kwargs['operations']
        self.plugins = kwargs['plugins']
        self.relationships = kwargs['relationships']
        self.plugins_to_install = kwargs['plugins_to_install']


class DeploymentNodeInstance(SerializableObject):
    """
    Represents a node instance in a deployment.
    """

    fields = {
        'id', 'deployment_id', 'runtime_properties', 'state', 'version',
        'relationships', 'node_id', 'host_id'
    }

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.node_id = kwargs['node_id']
        self.deployment_id = kwargs['deployment_id']
        self.runtime_properties = kwargs['runtime_properties']
        self.state = kwargs['state']
        self.version = kwargs['version']
        self.relationships = kwargs['relationships']
        self.host_id = kwargs['host_id']


class ProviderContext(SerializableObject):

    fields = {'context', 'name'}

    def __init__(self, **kwargs):
        self.context = kwargs['context']
        self.name = kwargs['name']


class Plugin(SerializableObject):
    """
    Represents a wheel plugin
    """
    fields = {'id', 'package_name', 'archive_name', 'package_source',
              'package_version', 'supported_platform', 'distribution',
              'distribution_version', 'distribution_release', 'wheels',
              'excluded_wheels', 'supported_py_versions', 'uploaded_at'}

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.package_name = kwargs['package_name']
        self.archive_name = kwargs['archive_name']
        self.package_source = kwargs['package_source']
        self.package_version = kwargs['package_version']
        self.supported_platform = kwargs['supported_platform']
        self.distribution = kwargs['distribution']
        self.distribution_version = kwargs['distribution_version']
        self.distribution_release = kwargs['distribution_release']
        self.wheels = kwargs['wheels']
        self.excluded_wheels = kwargs['excluded_wheels']
        self.supported_py_versions = kwargs['supported_py_versions']
        self.uploaded_at = kwargs['uploaded_at']


class Agent(SerializableObject):

    fields = {
        'id', 'deployment_id', 'node_id', 'alive', 'installable',
        'last_validation_timestamp', 'validated', 'state'
    }

    def __init__(self, **kwargs):
        for field in self.fields:
            setattr(self, field, kwargs[field])

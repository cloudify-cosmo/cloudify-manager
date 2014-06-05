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

__author__ = 'ran'

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

    fields = {'plan', 'id', 'source', 'created_at', 'updated_at'}

    def __init__(self, **kwargs):
        self.plan = kwargs['plan']
        self.id = kwargs['id']
        self.source = kwargs['source']
        self.created_at = kwargs['created_at']
        self.updated_at = kwargs['updated_at']


class Deployment(SerializableObject):

    fields = {'id', 'created_at', 'updated_at', 'blueprint_id', 'plan',
              'permalink'}

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.created_at = kwargs['created_at']
        self.updated_at = kwargs['updated_at']
        self.blueprint_id = kwargs['blueprint_id']
        self.plan = kwargs['plan']
        self.permalink = None  # TODO: implement


class Execution(SerializableObject):

    fields = {'id', 'status', 'deployment_id', 'internal_workflow_id',
              'workflow_id', 'blueprint_id', 'created_at', 'error'}

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.status = kwargs['status']
        self.deployment_id = kwargs['deployment_id']
        self.internal_workflow_id = kwargs['internal_workflow_id']
        self.workflow_id = kwargs['workflow_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.created_at = kwargs['created_at']
        self.error = kwargs['error']


class DeploymentNode(SerializableObject):
    """
    Represents an instance of a deployment node.
    """

    fields = {
        'id', 'deployment_id', 'blueprint_id', 'type', 'type_hierarchy',
        'number_of_instances', 'host_id', 'properties',
        'operations', 'plugins'
    }

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.deployment_id = kwargs['deployment_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.type = kwargs['type']
        self.type_hierarchy = kwargs['type_hierarchy']
        self.number_of_instances = kwargs['number_of_instances']
        self.host_id = kwargs['host_id']
        self.properties = kwargs['properties']
        self.operations = kwargs['operations']
        self.plugins = kwargs['plugins']


class DeploymentNodeInstance(SerializableObject):
    """
    Represents a node of a deployment.
    """

    fields = {
        'id', 'deployment_id', 'runtime_properties', 'state', 'version'
    }

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.deployment_id = kwargs['deployment_id']
        self.runtime_properties = kwargs['runtime_properties']
        self.state = kwargs['state']
        self.version = kwargs['version']


class ProviderContext(SerializableObject):

    fields = {'context', 'name'}

    def __init__(self, **kwargs):
        self.context = kwargs['context']
        self.name = kwargs['name']

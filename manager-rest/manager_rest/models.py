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
        attr_and_values = ((attr, getattr(self, attr)) for attr in dir(self)
                           if not attr.startswith("__"))
        return {attr: value for attr, value in
                attr_and_values if not callable(value)}

    def to_json(self):
        return json.dumps(self.to_dict())


class BlueprintState(SerializableObject):

    def __init__(self, *args, **kwargs):
        self.plan = kwargs['plan']
        self.id = self.plan['name']
        self.created_at = kwargs['created_at']
        self.updated_at = kwargs['updated_at']


class Deployment(SerializableObject):

    def __init__(self, *args, **kwargs):
        self.id = kwargs['id']
        self.created_at = kwargs['created_at']
        self.updated_at = kwargs['updated_at']
        self.blueprint_id = kwargs['blueprint_id']
        self.plan = kwargs['plan']
        self.permalink = None  # TODO: implement


class Execution(SerializableObject):

    def __init__(self, *args, **kwargs):
        self.id = kwargs['id']
        self.status = kwargs['status']
        self.deployment_id = kwargs['deployment_id']
        self.internal_workflow_id = kwargs['internal_workflow_id']
        self.workflow_id = kwargs['workflow_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.created_at = kwargs['created_at']
        self.error = kwargs['error']


class DeploymentNode(SerializableObject):

    def __init__(self, *args, **kwargs):
        self.id = kwargs['id']
        self.runtime_info = \
            kwargs['runtime_info'] if 'runtime_info' in kwargs else None
        self.reachable = kwargs['reachable'] if 'reachable' in kwargs else None
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

__author__ = 'idanmo'


class DictStorageManager(object):
    """
    In-memory dict based storage manager for tests.
    """

    def __init__(self):
        self._nodes = dict()
        self._blueprints = dict()
        self._executions = dict()
        self._deployments = dict()

    def get_nodes(self):
        return map(lambda x: {'id': x}, self._nodes.keys())

    def get_node(self, node_id):
        if node_id in self._nodes:
            return self._nodes[node_id]
        return {}

    def put_node(self, node_id, runtime_info):
        self._nodes[node_id] = runtime_info
        return runtime_info

    def update_node(self, node_id, updated_properties):
        runtime_info = self._nodes[node_id].copy() if node_id\
            in self._nodes else {}
        for key, value in updated_properties.iteritems():
            if len(value) == 1:
                if key in runtime_info:
                    raise RuntimeError("Node update conflict - key: '{0}'"
                                       " is not expected to exist"
                                       .format(key))
            elif len(value) == 2:
                if key not in runtime_info:
                    raise RuntimeError("Node update conflict - key: '{0}'"
                                       " is expected to exist".format(key))
                if runtime_info[key] != value[1]:
                    raise RuntimeError(
                        "Node update conflict - key: '{0}' value is "
                        "expected to be '{1}' but is '{2}'"
                        .format(key, value[1], runtime_info[key]))
            runtime_info[key] = value[0]
        self._nodes[node_id] = runtime_info
        return runtime_info

    def blueprints_list(self):
        return self._blueprints.values()

    def deployments_list(self):
        return self._deployments.values()

    def get_blueprint(self, blueprint_id):
        return self._blueprints.get(blueprint_id, None)

    def get_deployment(self, deployment_id):
        return self._deployments.get(deployment_id, None)

    def get_execution(self, execution_id):
        return self._executions.get(execution_id, None)

    def put_blueprint(self, blueprint_id, blueprint):
        if str(blueprint_id) in self._blueprints:
            raise RuntimeError('Blueprint {0} already exists'.format(
                blueprint_id))
        self._blueprints[str(blueprint_id)] = blueprint

    def put_deployment(self, deployment_id, deployment):
        if str(deployment_id) in self._deployments:
            raise RuntimeError('Deployment {0} already exists'.format(
                deployment_id))
        self._deployments[str(deployment_id)] = deployment

    def put_execution(self, execution_id, execution):
        if str(execution_id) in self._executions:
            raise RuntimeError('Execution {0} already exists'.format(
                execution_id))
        self._executions[str(execution_id)] = execution

    def add_execution_to_deployment(self, deployment_id, execution):
        if str(deployment_id) not in self._deployments:
            raise RuntimeError("Deployment {0} doesn't exist".format(
                deployment_id))
        self._deployments[str(deployment_id)].add_execution(execution)


def create():
    return DictStorageManager()

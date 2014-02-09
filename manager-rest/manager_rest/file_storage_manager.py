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

import os
import json
import serialization

STORAGE_FILE_PATH = '/tmp/manager-rest-tests-storage.json'

NODES = 'nodes'
BLUEPRINTS = 'blueprints'
DEPLOYMENTS = 'deployments'
EXECUTIONS = 'executions'


class FileStorageManager(object):
    """
    file based storage manager for tests.
    """

    def __init__(self, storage_path):
        self._storage_path = storage_path
        if os.path.isfile(storage_path):
            os.remove(storage_path)

    def _init_file(self):
        data = {
            NODES: {},
            BLUEPRINTS: {},
            DEPLOYMENTS: {},
            EXECUTIONS: {}
        }
        self._dump_data(data)

    def _load_data(self):
        if not os.path.isfile(self._storage_path):
            self._init_file()
        with open(self._storage_path, 'r') as f:
            data = json.load(f)
            return serialization.deserialize_object(data)

    def _dump_data(self, data):
        with open(self._storage_path, 'w') as f:
            data = serialization.serialize_object(data)
            json.dump(data, f)

    def get_nodes(self):
        data = self._load_data()
        return map(lambda x: {'id': x}, data[NODES].keys())

    def get_node(self, node_id):
        data = self._load_data()
        if node_id in data[NODES]:
            return data[NODES][node_id]
        return {}

    def put_node(self, node_id, runtime_info):
        data = self._load_data()
        data[NODES][node_id] = runtime_info
        self._dump_data(data)
        return runtime_info

    def update_node(self, node_id, updated_properties):
        data = self._load_data()
        runtime_info = data[NODES][node_id].copy() if node_id \
            in data[NODES] else {}
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
        data[NODES][node_id] = runtime_info
        self._dump_data(data)
        return runtime_info

    def blueprints_list(self):
        data = self._load_data()
        return data[BLUEPRINTS].values()

    def deployments_list(self):
        data = self._load_data()
        return data[DEPLOYMENTS].values()

    def executions_list(self):
        data = self._load_data()
        return data[EXECUTIONS].values()

    def get_deployment_executions(self, deployment_id):
        executions = self.executions_list()
        return [execution for execution in executions if execution
                .deployment_id == deployment_id]

    def get_blueprint(self, blueprint_id):
        data = self._load_data()
        return data[BLUEPRINTS].get(blueprint_id, None)

    def get_deployment(self, deployment_id):
        data = self._load_data()
        return data[DEPLOYMENTS].get(deployment_id, None)

    def get_execution(self, execution_id):
        data = self._load_data()
        return data[EXECUTIONS].get(execution_id, None)

    def put_blueprint(self, blueprint_id, blueprint):
        data = self._load_data()
        if str(blueprint_id) in data[BLUEPRINTS]:
            raise RuntimeError('Blueprint {0} already exists'.format(
                blueprint_id))
        data[BLUEPRINTS][str(blueprint_id)] = blueprint
        self._dump_data(data)

    def put_deployment(self, deployment_id, deployment):
        data = self._load_data()
        if str(deployment_id) in data[DEPLOYMENTS]:
            raise RuntimeError('Deployment {0} already exists'.format(
                deployment_id))
        data[DEPLOYMENTS][str(deployment_id)] = deployment
        self._dump_data(data)

    def put_execution(self, execution_id, execution):
        data = self._load_data()
        if str(execution_id) in data[EXECUTIONS]:
            raise RuntimeError('Execution {0} already exists'.format(
                execution_id))
        data[EXECUTIONS][str(execution_id)] = execution
        self._dump_data(data)


def create():
    return FileStorageManager(STORAGE_FILE_PATH)

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
from models import BlueprintState, Deployment, Execution, \
    DeploymentNode
import manager_rest.manager_exceptions

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
            deserialized_data = dict()
            deserialized_data[NODES] = \
                {key: DeploymentNode(**val) for key, val in data[NODES]
                    .iteritems()}
            deserialized_data[BLUEPRINTS] = \
                {key: BlueprintState(**val) for key, val in data[BLUEPRINTS]
                    .iteritems()}
            deserialized_data[DEPLOYMENTS] = \
                {key: Deployment(**val) for key, val in data[DEPLOYMENTS]
                    .iteritems()}
            deserialized_data[EXECUTIONS] = \
                {key: Execution(**val) for key, val in data[EXECUTIONS]
                    .iteritems()}
            return deserialized_data

    def _dump_data(self, data):
        with open(self._storage_path, 'w') as f:
            serialized_data = dict()
            serialized_data[NODES] = {key: val.to_dict() for key, val in
                                      data[NODES].iteritems()}
            serialized_data[BLUEPRINTS] =\
                {key: val.to_dict() for key, val in data[BLUEPRINTS]
                    .iteritems()}
            serialized_data[DEPLOYMENTS] =\
                {key: val.to_dict() for key, val in data[DEPLOYMENTS]
                    .iteritems()}
            serialized_data[EXECUTIONS] =\
                {key: val.to_dict() for key, val in data[EXECUTIONS]
                    .iteritems()}
            json.dump(serialized_data, f)

    def nodes_list(self):
        data = self._load_data()
        return data[NODES].values()

    def get_node(self, node_id):
        data = self._load_data()
        if node_id in data[NODES]:
            return data[NODES][node_id]
        raise manager_rest.manager_exceptions.NotFoundError(
            "Node {0} not found".format(node_id))

    def put_node(self, node_id, node):
        data = self._load_data()
        if str(node_id) in data[NODES]:
            raise manager_rest.manager_exceptions.ConflictError(
                'Node {0} already exists'.format(node_id))
        data[NODES][str(node_id)] = node
        self._dump_data(data)

    def update_node(self, node_id, node):
        data = self._load_data()
        if node_id not in data[NODES]:
            self.put_node(node_id, node)
            return

        prev_rt_info = DeploymentNode(**data[NODES][node_id].to_dict())\
            .runtime_info
        merged_rt_info = dict(prev_rt_info.items() +
                              node.runtime_info.items())
        #TODO: merge reachable field?
        node = DeploymentNode(id=node_id, runtime_info=merged_rt_info)
        data[NODES][node_id] = node
        self._dump_data(data)

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
        if blueprint_id in data[BLUEPRINTS]:
            return data[BLUEPRINTS][blueprint_id]
        raise manager_rest.manager_exceptions.NotFoundError(
            "Blueprint {0} not found".format(blueprint_id))

    def get_deployment(self, deployment_id):
        data = self._load_data()
        if deployment_id in data[DEPLOYMENTS]:
            return data[DEPLOYMENTS][deployment_id]
        raise manager_rest.manager_exceptions.NotFoundError(
            "Deployment {0} not found".format(deployment_id))

    def get_execution(self, execution_id):
        data = self._load_data()
        if execution_id in data[EXECUTIONS]:
            return data[EXECUTIONS][execution_id]
        raise manager_rest.manager_exceptions.NotFoundError(
            "Execution {0} not found".format(execution_id))

    def put_blueprint(self, blueprint_id, blueprint):
        data = self._load_data()
        if str(blueprint_id) in data[BLUEPRINTS]:
            raise manager_rest.manager_exceptions.ConflictError(
                'Blueprint {0} already exists'.format(blueprint_id))
        data[BLUEPRINTS][str(blueprint_id)] = blueprint
        self._dump_data(data)

    def put_deployment(self, deployment_id, deployment):
        data = self._load_data()
        if str(deployment_id) in data[DEPLOYMENTS]:
            raise manager_rest.manager_exceptions.ConflictError(
                'Deployment {0} already exists'.format(deployment_id))
        data[DEPLOYMENTS][str(deployment_id)] = deployment
        self._dump_data(data)

    def put_execution(self, execution_id, execution):
        data = self._load_data()
        if str(execution_id) in data[EXECUTIONS]:
            raise manager_rest.manager_exceptions.ConflictError(
                'Execution {0} already exists'.format(execution_id))
        data[EXECUTIONS][str(execution_id)] = execution
        self._dump_data(data)


def create():
    return FileStorageManager(STORAGE_FILE_PATH)

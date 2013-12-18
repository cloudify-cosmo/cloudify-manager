########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'idanmo'


import os
import requests


def _get_base_uri():
    return "http://localhost:{0}".format(os.environ['MANAGER_REST_PORT'])


class DeploymentNode(object):

    def __init__(self, node_id, runtime_properties=None):
        self._id = node_id
        self._runtime_properties = runtime_properties
        if runtime_properties is not None:
            self._runtime_properties = {k: [v, None] for k, v in runtime_properties.iteritems()}

    def get(self, key):
        return self._runtime_properties[key][0]

    def put(self, key, value):
        if self._runtime_properties is None:
            self._runtime_properties = {}
        if key in self._runtime_properties:
            values = self._runtime_properties[key]
            if len(values) == 1:
                self._runtime_properties[key] = [value, values[0]]
            else:
                values[0] = value
        else:
            self._runtime_properties[key] = [value]

    def get_updated_properties(self):
        if self._runtime_properties is None:
            return {}
        return {k: v for k, v in self._runtime_properties.iteritems() if len(v) == 1 or v[1] is not None}


def get_node_state(node_id):
    response = requests.get("{0}/nodes/{1}".format(_get_base_uri(), node_id))
    if response.status_code != 200:
        raise RuntimeError(
            "Error getting node from cloudify runtime for node id {0} [code={1}]".format(node_id, response.status_code))
    return DeploymentNode(node_id, response.json['runtimeInfo'])


def update_node_state(node):

    response = requests.put("{0}/nodes{1}".format(_get_base_uri(), node['id']), node)
    if response.status_code != 200:
        raise RuntimeError(
            "Error getting node from cloudify runtime for node id {0} [code={1}]".format(node['id'],
                                                                                         response.status_code))
    return response.json

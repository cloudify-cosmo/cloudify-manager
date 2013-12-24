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


CLOUDIFY_ID_PROPERTY = '__cloudify_id'
CLOUDIFY_NODE_STATE_PROPERTY = 'node_state'


def _get_base_uri():
    return "http://localhost:{0}".format(os.environ['MANAGER_REST_PORT'])


class DeploymentNode(object):

    def __init__(self, node_id, runtime_properties=None):
        self.id = node_id
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


# TODO runtime-model: use manager-rest-client
def get_node_state(node_id):
    response = requests.get("{0}/nodes/{1}".format(_get_base_uri(), node_id))
    if response.status_code != 200:
        raise RuntimeError(
            "Error getting node from cloudify runtime for node id {0} [code={1}]".format(node_id, response.status_code))
    return DeploymentNode(node_id, response.json()['runtimeInfo'])


# TODO runtime-model: use manager-rest-client
def update_node_state(node_state):
    updated_properties = node_state.get_updated_properties()
    if len(updated_properties) == 0:
        return None
    import json
    response = requests.patch("{0}/nodes/{1}".format(_get_base_uri(), node_state.id),
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(updated_properties))
    if response.status_code != 200:
        raise RuntimeError(
            "Error getting node from cloudify runtime for node id {0} [code={1}]".format(node_state.id,
                                                                                         response.status_code))
    return response.json()


def inject_node_state(task):
    def task_wrapper(*args, **kwargs):
        node_id = _get_cloudify_id_from_method_arguments(task, args, kwargs)
        state = None
        if node_id is not None:
            try:
                state = get_node_state(node_id)
            except Exception:
                # TODO: log exception
                pass
            kwargs[CLOUDIFY_NODE_STATE_PROPERTY] = state
        task(*args, **kwargs)
        if state is not None:
            try:
                update_node_state(state)
            except Exception as e:
                # TODO: log exception
                pass
    return task_wrapper


def _get_cloudify_id_from_method_arguments(method, args, kwargs):
    if CLOUDIFY_ID_PROPERTY in kwargs:
        return kwargs[CLOUDIFY_ID_PROPERTY]
    try:
        arg_index = method.func_code.co_varnames.index(CLOUDIFY_ID_PROPERTY)
        return args[arg_index]
    except ValueError:
        pass
    return None


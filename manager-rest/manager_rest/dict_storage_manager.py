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

__author__ = 'idanm'


from responses import Nodes
from responses import Node
from threading import Lock


class DictStorageManager(object):
    """
    In-memory dict based storage manager for tests.
    """

    def __init__(self):
        self._storage = dict()
        self._lock = Lock()

    def get_nodes(self):
        with self._lock:
            return Nodes(nodes=map(lambda x: {'id': x}, self._storage.keys()))

    def get_node(self, node_id):
        with self._lock:
            if node_id in self._storage:
                return Node(id=node_id, runtime_info=self._storage[node_id])
            return Node(id=node_id, runtime_info={})

    def put_node(self, node_id, runtime_info):
        with self._lock:
            self._storage[node_id] = runtime_info
            return Node(id=node_id, runtime_info=runtime_info)

    def update_node(self, node_id, updated_properties):
        with self._lock:
            runtime_info = self._storage[node_id].copy() if node_id in self._storage else {}
            for key, value in updated_properties.iteritems():
                if len(value) == 1:
                    if key in runtime_info:
                        raise RuntimeError("Node update conflict - key: '{0}' is not expected to exist".format(key))
                elif len(value) == 2:
                    if key not in runtime_info:
                        raise RuntimeError("Node update conflict - key: '{0}' is expected to exist".format(key))
                    if runtime_info[key] != value[1]:
                        raise RuntimeError(
                            "Node update conflict - key: '{0}' value is expected to be '{1}' but is '{2}'".format(
                                key, value[1], runtime_info[key]))
                runtime_info[key] = value[0]
            self._storage[node_id] = runtime_info
            return Node(id=node_id, runtime_info=runtime_info)


def create():
    return DictStorageManager()

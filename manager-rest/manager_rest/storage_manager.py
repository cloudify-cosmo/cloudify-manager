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


class StorageManager(object):
    """
    In-memory storage manager for tests.
    """

    def __init__(self):
        self._store = dict()

    def get_node(self, node_id):
        if self._store.has_key(node_id):
            return self._store[node_id]
        return {'runtime_info': {}, 'properties': {}}

    def put_node(self, node_id, runtime_info):
        self._store[node_id] = runtime_info


_instance = StorageManager()


def reset():
    global _instance
    _instance = StorageManager()


def instance():
    return _instance

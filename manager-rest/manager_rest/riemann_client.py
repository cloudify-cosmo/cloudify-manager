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


import bernhard


class RiemannClient(object):

    def __init__(self):
        self._client = bernhard.Client(host='localhost')

    def get_node_state(self, node_id):
        state = self._client.query('tagged "name={0}"'.format(node_id))
        if len(state) == 1:
            reachable = 'reachable' in state[0].tags
            return {'reachable': reachable}
        return {'reachable': False}


_instance = RiemannClient()


def instance():
    return _instance

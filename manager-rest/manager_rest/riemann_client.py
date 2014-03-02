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

from collections import defaultdict
import bernhard


class RiemannClient(object):
    """
    Riemann client.
    """

    def __init__(self):
        self._client = bernhard.Client(host='localhost')

    def get_node_state(self, node_id):
        """
        Get node reachable state.
        """
        return self.get_nodes_state([node_id])[node_id]

    def get_nodes_state(self, node_ids):
        """
        Get nodes reachable state.
        """
        node_result = {}

        or_query = ' or '

        # construct quest with or separator
        query = or_query.join('service = "{0}"'.format(node_id) for node_id in node_ids)

        for node_id in node_ids:
            node_result[node_id] = []

        raw_results = self._client.query(query)
        for raw_result in raw_results:
            raw_result_node_id = raw_result.service
            node_result[raw_result_node_id].append(raw_result)

        node_reachable_states = {}
        for node_id, states in node_result.iteritems():
            node_reachable_state = {'reachable': False}
            for state in states:
                host = state.host
                node_reachable_state = {'reachable': False, 'host': host}
                if 'started' in state.state:
                    node_reachable_state = {'reachable': True,
                                            'host': state.host}
                    break
            node_reachable_states[node_id] = node_reachable_state

        return node_reachable_states

    def teardown(self):
        self._client.disconnect()

_instance = RiemannClient()


def instance():
    return _instance

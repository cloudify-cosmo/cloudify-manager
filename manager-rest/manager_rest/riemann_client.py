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


import bernhard
from StringIO import StringIO


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
        query = StringIO()
        or_query = ' or '
        for node_id in node_ids:
            node_result[node_id] = []
            query.write('service = "{0}"{1}'.format(node_id, or_query))
        query.truncate(len(query.getvalue()) - len(or_query))

        raw_results = self._client.query(query.getvalue())
        for raw_result in raw_results:
            raw_result_node_id = raw_result.service
            node_result[raw_result_node_id].append(raw_result)
            with open("/tmp/idan.txt", "a") as f:
                aaa = "@@@@@@@@ service={0}, state={1}\n".format(raw_result.service, raw_result.state)
                f.write(aaa)

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

_instance = RiemannClient()


def instance():
    return _instance

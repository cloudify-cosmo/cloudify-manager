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
from manager_rest.util import maybe_register_teardown


__author__ = 'idanmo'

from flask import g, current_app

import bernhard


class RiemannClient(object):
    """
    Riemann client.
    """

    def __init__(self):
        self._client = bernhard.Client(host='localhost')
        # print "connected!"

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
        query = or_query.join('service = "{0}"'.format(node_id)
                              for node_id in node_ids)

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
        # print "disconnected!"


# What we need to access the client in Flask
def teardown_riemann(exception):
    """
    Disconnect Riemann at the end of the request
    """
    if 'riemann_client' in g:
        g.riemann_client.teardown()


def get_riemann_client():
    """
    Get the current riemann_client
    or create one if none exists for the current app context
    """
    if not 'riemann_client' in g:
        g.riemann_client = RiemannClient()
        maybe_register_teardown(current_app, teardown_riemann)

    return g.riemann_client

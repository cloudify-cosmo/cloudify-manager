########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import json
from os.path import join

from .utils import is_compute


class Networks(object):
    _NETWORKS = 'networks.json'

    def dump(self, tempdir, client):
        networks_dump_path = join(tempdir, self._NETWORKS)
        networks = self.get_networks_from_provider_context(client)
        active_networks = self._get_active_networks(client)
        output = {
            'networks': networks,
            'active_networks': list(active_networks)
        }
        with open(networks_dump_path, 'w') as f:
            json.dump(output, f)

    @staticmethod
    def get_networks_from_provider_context(client):
        """ Return the dict of networks from the provider context """

        context = client.manager.get_context()
        agent_config = context['context']['cloudify']['cloudify_agent']
        return agent_config['networks']

    @staticmethod
    def _get_compute_nodes(client):
        """ Return a set of the IDs of all the compute nodes """

        all_nodes = client.nodes.list(_all_tenants=True,
                                      _include=['id', 'type_hierarchy'],
                                      _get_all_results=True)
        return {node.id for node in all_nodes if is_compute(node)}

    @staticmethod
    def _get_active_node_instances(client, compute_nodes):
        active_node_instances = list()
        all_node_instances = client.node_instances.list(
            _all_tenants=True,
            _include=['node_id', 'state'],
            _get_all_results=True
        )
        for node_instance in all_node_instances:
            # Skip node instances that aren't instances of compute nodes
            if node_instance.node_id not in compute_nodes:
                continue
            # Skip any non-live agents
            if node_instance.state != 'started':
                continue
            active_node_instances.append(node_instance)
        return active_node_instances

    def _get_active_networks(self, client):
        active_networks = set()
        compute_nodes = self._get_compute_nodes(client)
        active_node_instances = self._get_active_node_instances(
            client,
            compute_nodes
        )
        for node_instance in active_node_instances:
            runtime_props = node_instance.runtime_properties

            # The node instance might not have an agent
            agent_config = runtime_props.get('cloudify_agent', {})
            network = agent_config.get('network')
            if network:
                active_networks.add(network)

        return active_networks

    @staticmethod
    def get_networks_from_snapshot(tempdir):
        networks_dump_path = join(tempdir, Networks._NETWORKS)
        with open(networks_dump_path, 'r') as f:
            return json.load(f)

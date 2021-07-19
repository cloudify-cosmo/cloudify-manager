########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

import os
import json

from cloudify.workflows import ctx
from cloudify import broker_config
from cloudify.manager import get_rest_client
from cloudify.models_states import AgentState
from cloudify.utils import get_broker_ssl_cert_path
from cloudify.agent_utils import create_agent_record
from cloudify.constants import AGENT_INSTALL_METHOD_NONE
from cloudify_rest_client.exceptions import CloudifyClientError

from .constants import V_4_1_0, V_4_4_0, V_4_5_5


class Agents(object):
    _AGENTS_FILE = 'agents.json'

    def __init__(self):
        with open(get_broker_ssl_cert_path(), 'r') as f:
            self._broker_ssl_cert = f.read()
        self._manager_version = None

    def restore(self, tempdir, version):
        with open(os.path.join(tempdir, self._AGENTS_FILE)) as agents_file:
            agents = json.load(agents_file)
        self._manager_version = version
        if version < V_4_1_0:
            self._insert_agents_data(agents)
            return
        for tenant_name, deployments in agents.items():
            self._insert_agents_data(agents[tenant_name], tenant_name)

    def dump(self, tempdir, manager_version):
        self._manager_version = manager_version
        result = {}
        client = get_rest_client()
        agents = client.agents.list(_all_tenants=True)
        agent_ids = [agent.id for agent in agents.items]
        node_instances = client.node_instances.search(
            agent_ids, all_tenants=True)
        for instance in node_instances:
            self._add_node_instance_to_result(instance, result)
        self._dump_result_to_file(tempdir, result)

    def _add_node_instance_to_result(self, instance, result):
        result.setdefault(instance['tenant_name'], {})
        tenant = result[instance['tenant_name']]
        tenant.setdefault(instance['deployment_id'], {})
        deployment = tenant[instance['deployment_id']]
        deployment.setdefault(instance['node_id'], {})
        node = deployment[instance['node_id']]
        node[instance['id']] = self._get_node_instance_result(instance)

    def _dump_result_to_file(self, tempdir, result):
        agents_file_path = os.path.join(tempdir, self._AGENTS_FILE)
        with open(agents_file_path, 'w') as out:
            out.write(json.dumps(result))

    def _get_node_instance_result(self, node_instance):
        """
        Fill in the broker config info from the cloudify_agent dict, using
        the info from the bootstrap context as the fallback defaults
        """
        agent = node_instance.runtime_properties.get('cloudify_agent', {})
        broker_conf = {
            'broker_ip': agent.get('broker_ip', broker_config.broker_hostname),
            'broker_ssl_cert': self._broker_ssl_cert,
            'broker_ssl_enabled': True
        }
        return {
            'version': str(self._manager_version),
            'broker_config': broker_conf
        }

    def _insert_agents_data(self, agents, tenant_name=None):
        for deployment_id, nodes in agents.items():
            try:
                self._create_agent(nodes, tenant_name)
            except Exception:
                ctx.logger.warning(
                    'Failed restoring agents for deployment `{0}` in tenant '
                    '`{1}`'.format(deployment_id, tenant_name),
                    exc_info=True)

    @classmethod
    def _get_tenant_name(cls, node_instance_id):
        """
        When restoring a snapshot from versions 4.0.0/4.0.1 the tenant name is
        not defined and the only way to `guess` it is by finding the
        node_instance from the agents.json file in the DB and checking its
        tenant. Using list to scan all tenants and filter by id.
        :param node_instance_id: a node instance from the agents.json file
        :return: the tenant of the given node instance
        """
        client = get_rest_client()
        try:
            node_instance = client.node_instances.list(
                _all_tenants=True, id=node_instance_id).items[0]
            return node_instance['tenant_name']
        except CloudifyClientError:
            pass

    def _create_agent(self, nodes, tenant_name):
        client = None
        for node_instances in nodes.values():
            for node_instance_id, agent in node_instances.items():
                broker_config = self._get_broker_config(agent)
                tenant_name = tenant_name or self._get_tenant_name(
                    node_instance_id)
                client = client or get_rest_client(tenant_name)
                node_instance = client.node_instances.get(node_instance_id)
                runtime_properties = node_instance.runtime_properties
                old_agent = runtime_properties.get('cloudify_agent', {})
                self.insert_agent_to_db(old_agent, node_instance_id, client)
                if not broker_config.get('broker_ip'):
                    broker_config['broker_ip'] = \
                        old_agent.get('manager_ip', '')
                agent['broker_config'] = broker_config
                old_agent.update(agent)
                runtime_properties['cloudify_agent'] = old_agent
                # Results of agent validation on old manager.
                # Might be incorrect for new manager.
                runtime_properties.pop('agent_status', None)
                # Starting from version 4.4 the rest_tenant is not being saved
                # in the runtime properties
                if self._manager_version < V_4_4_0:
                    runtime_properties.pop('rest_tenant', None)
                client.node_instances.update(
                    node_instance_id=node_instance_id,
                    runtime_properties=runtime_properties,
                    version=node_instance.version
                )

    def insert_agent_to_db(self, cloudify_agent, node_instance_id, client):
        # Add an agent to the db if the snapshot is from a version with no
        # agents table
        if self._manager_version >= V_4_5_5:
            return
        cloudify_agent['node_instance_id'] = node_instance_id
        cloudify_agent['version'] = cloudify_agent.get('version') or \
            str(self._manager_version)
        cloudify_agent.pop('broker_user', None)
        cloudify_agent.pop('broker_pass', None)
        install_method = cloudify_agent.get('install_method')
        if install_method and install_method != AGENT_INSTALL_METHOD_NONE:
            create_agent_record(cloudify_agent,
                                state=AgentState.RESTORED,
                                client=client)

    @staticmethod
    def _get_broker_config(agent):
        # We need to retrieve broker_config:
        # 3.3.1 and later
        if 'broker_config' in agent:
            broker_config = agent['broker_config']
        # 3.3 and earlier
        else:
            broker_config = {}
            for k in ['broker_user', 'broker_pass', 'broker_ip',
                      'broker_ssl_enabled', 'broker_ssl_cert']:
                broker_config[k] = agent.pop(k)
            if broker_config['broker_ssl_enabled']:
                broker_config['broker_port'] = '5671'
            else:
                broker_config['broker_port'] = '5672'
        return broker_config

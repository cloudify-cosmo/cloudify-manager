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

import os
import json

from cloudify.workflows import ctx
from cloudify import broker_config
from cloudify.manager import get_rest_client
from cloudify.utils import get_broker_ssl_cert_path

from .utils import is_compute, get_tenants_list
from .constants import BROKER_DEFAULT_VHOST, V_4_1_0


class Agents(object):
    _AGENTS_FILE = 'agents.json'

    def __init__(self):
        with open(get_broker_ssl_cert_path(), 'r') as f:
            self._broker_ssl_cert = f.read()

    def restore(self, tempdir, version):
        with open(os.path.join(tempdir, self._AGENTS_FILE)) as agents_file:
            agents = json.load(agents_file)
        if version < V_4_1_0:
            self._insert_agents_data(agents)
            return
        for tenant_name, deployments in agents.iteritems():
            self._insert_agents_data(agents[tenant_name], tenant_name)

    def dump(self, tempdir, manager_version):
        self._manager_version = manager_version
        result = {}
        for tenant_name in get_tenants_list():
            result[tenant_name] = {}
            tenant_client = get_rest_client(tenant_name)
            tenant_deployments = tenant_client.deployments.list()
            for deployment in tenant_deployments:
                result[tenant_name][deployment.id] = \
                    self._get_deployment_result(tenant_client, deployment.id)
        self._dump_result_to_file(tempdir, result)

    def _dump_result_to_file(self, tempdir, result):
        agents_file_path = os.path.join(tempdir, self._AGENTS_FILE)
        with open(agents_file_path, 'w') as out:
            out.write(json.dumps(result))

    def _get_deployment_result(self, client, deployment_id):
        deployment_result = {}
        for node in client.nodes.list(deployment_id=deployment_id):
            if is_compute(node):
                deployment_result[node.id] = self._get_node_result(
                    client, deployment_id, node.id)
        return deployment_result

    def _get_node_result(self, client, deployment_id, node_id):
        node_result = {}
        for node_instance in client.node_instances.list(
                deployment_id=deployment_id, node_name=node_id):
            node_result[node_instance.id] = self._get_node_instance_result(
                node_instance)
        return node_result

    def _get_node_instance_result(self, node_instance):
        """
        Fill in the broker config info from the cloudify_agent dict, using
        the info from the bootstrap context as the fallback defaults
        """
        agent = node_instance.runtime_properties.get('cloudify_agent', {})
        tenant = agent.get('rest_tenant', {})
        broker_conf = {
            'broker_ip': agent.get('broker_ip', broker_config.broker_hostname),
            'broker_ssl_cert': self._broker_ssl_cert,
            'broker_ssl_enabled': True,
            'broker_user': tenant.get('rabbitmq_username',
                                      broker_config.broker_username),
            'broker_pass': tenant.get('rabbitmq_password',
                                      broker_config.broker_password),
            'broker_vhost': tenant.get('rabbitmq_vhost',
                                       broker_config.broker_vhost)
        }
        return {
            'version': str(self._manager_version),
            'broker_config': broker_conf
        }

    def _insert_agents_data(self, agents, tenant_name=None):
        for deployment_id, nodes in agents.iteritems():
            try:
                self._create_agent(nodes, tenant_name)
            except Exception:
                ctx.logger.warning(
                    'Failed restoring agents for deployment `{0}` in tenant '
                    '`{1}`'.format(deployment_id, tenant_name),
                    exc_info=True)

    def _create_rest_tenant(self, old_agent, broker_config, tenant_name):
        old_rest_tenant = old_agent.get('rest_tenant', tenant_name)
        if isinstance(old_rest_tenant, dict):
            return old_rest_tenant
        return {
            'rabbitmq_vhost': broker_config['broker_vhost'],
            'rabbitmq_username': broker_config['broker_user'],
            'rabbitmq_password': broker_config['broker_pass'],
            'name': old_rest_tenant
        }

    @classmethod
    def _get_tenant_name(cls, node_instance_id):
        """
        When restoring a snapshot from versions 4.0.0/4.0.1 the tenant name is
        not defined and the only way to `guess` it is by finding the
        node_instance from the agents.json file in the DB and checking its
        tenant.
        :param node_instance_id: a node instance from the agents.json file
        :return: the tenant of the given node instance
        """
        client = get_rest_client()
        node_instances = client.node_instances.list(_all_tenants=True).items
        for node_instance in node_instances:
            if node_instance['id'] == node_instance_id:
                return node_instance['tenant_name']

    def _create_agent(self, nodes, tenant_name):
        client = None
        for node_instances in nodes.itervalues():
            for node_instance_id, agent in node_instances.iteritems():
                broker_config = self._get_broker_config(agent)
                tenant_name = tenant_name or self._get_tenant_name(
                    node_instance_id)
                client = client or get_rest_client(tenant_name)
                node_instance = client.node_instances.get(node_instance_id)
                runtime_properties = node_instance.runtime_properties
                old_agent = runtime_properties.get('cloudify_agent', {})
                if not broker_config.get('broker_ip'):
                    broker_config['broker_ip'] = \
                        old_agent.get('manager_ip', '')
                broker_config['broker_vhost'] = \
                    broker_config.get('broker_vhost', BROKER_DEFAULT_VHOST)
                agent['rest_tenant'] = self._create_rest_tenant(
                    old_agent, broker_config, tenant_name)
                agent['broker_config'] = broker_config
                old_agent.update(agent)
                runtime_properties['cloudify_agent'] = old_agent
                # Results of agent validation on old manager.
                # Might be incorrect for new manager.
                runtime_properties.pop('agent_status', None)
                client.node_instances.update(
                    node_instance_id=node_instance_id,
                    runtime_properties=runtime_properties,
                    version=node_instance.version
                )

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

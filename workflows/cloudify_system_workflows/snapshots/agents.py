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
from cloudify.context import BootstrapContext
from cloudify.utils import get_broker_ssl_cert_path

from .utils import is_compute


class Agents(object):
    _AGENTS_FILE = 'agents.json'

    def restore(self, tempdir, client):
        with open(os.path.join(tempdir, self._AGENTS_FILE)) as agents_file:
            agents = json.load(agents_file)
        self._insert_agents_data(client, agents)

    def dump(self, tempdir, client, manager_version):
        result = {}
        defaults = self._get_defaults(manager_version)
        for deployment in client.deployments.list():
            deployment_result = self._get_deployment_result(
                client,
                deployment.id,
                defaults
            )
            result[deployment.id] = deployment_result

        self._dump_result_to_file(tempdir, result)

    def _dump_result_to_file(self, tempdir, result):
        agents_file_path = os.path.join(tempdir, self._AGENTS_FILE)
        with open(agents_file_path, 'w') as out:
            out.write(json.dumps(result))

    @staticmethod
    def _get_defaults(manager_version):
        broker_config = BootstrapContext(ctx.bootstrap_context).broker_config()
        if not broker_config.get('broker_ssl_cert'):
            with open(get_broker_ssl_cert_path(), 'r') as f:
                broker_config['broker_ssl_cert'] = f.read()

        return {
            'version': str(manager_version),
            'broker_config': broker_config
        }

    def _get_deployment_result(self, client, deployment_id, defaults):
        deployment_result = {}
        for node in client.nodes.list(deployment_id=deployment_id):
            if is_compute(node):
                node_result = self._get_node_result(
                    client,
                    deployment_id,
                    node.id,
                    defaults
                )
                deployment_result[node.id] = node_result
        return deployment_result

    def _get_node_result(self, client, deployment_id, node_id, defaults):
        node_result = {}
        for node_instance in client.node_instances.list(
                deployment_id=deployment_id,
                node_name=node_id):
            node_instance_result = self._get_node_instance_result(
                node_instance,
                defaults)
            node_result[node_instance.id] = node_instance_result
        return node_result

    @staticmethod
    def _get_node_instance_result(node_instance, defaults):
        node_instance_result = {}
        current = node_instance.runtime_properties.get('cloudify_agent', {})
        for k, v in defaults.iteritems():
            node_instance_result[k] = current.get(k, v)
        return node_instance_result

    def _insert_agents_data(self, client, agents):
        for deployment_id, nodes in agents.iteritems():
            try:
                self._create_agent(client, nodes)
            except Exception:
                ctx.logger.warning('Failed restoring agents for '
                                   'deployment {0}'.format(deployment_id),
                                   exc_info=True)

    def _create_agent(self, client, nodes):
        for node_instances in nodes.itervalues():
            for node_instance_id, agent in node_instances.iteritems():
                broker_config = self._get_broker_config(agent)
                node_instance = client.node_instances.get(node_instance_id)
                runtime_properties = node_instance.runtime_properties
                old_agent = runtime_properties.get('cloudify_agent', {})
                if not broker_config.get('broker_ip'):
                    broker_config['broker_ip'] = \
                        old_agent.get('manager_ip', '')
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

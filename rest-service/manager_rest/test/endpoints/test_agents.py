########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

from cloudify.models_states import AgentState
from cloudify.cryptography_utils import encrypt
from cloudify.utils import generate_user_password

from manager_rest.test import base_test
from manager_rest import manager_exceptions
from manager_rest.test.attribute import attr
from manager_rest.test.mocks import put_node_instance
from manager_rest.utils import get_formatted_timestamp
from manager_rest.storage.models import Agent, NodeInstance

from cloudify_rest_client.exceptions import CloudifyClientError


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class AgentsTest(base_test.BaseServerTestCase):
    agent_data = {
        'install_method': 'remote',
        'version': '4.5.5',
        'rabbitmq_exchange': 'agent_1'
    }

    def test_get_agent(self):
        self.put_agent()
        agent = self.client.agents.get('agent_1')
        self.assertEqual(agent.name, 'agent_1')
        self.assertEqual(agent.node_instance_id, 'node_instance_1')
        self.assertEqual(agent.ip, '127.0.0.1')
        self.assertEqual(agent.install_method, 'remote')
        self.assertEqual(agent.system, 'centos core')

    def test_get_invalid_agent_name(self):
        error_message = '400: The `name` argument contains illegal characters'
        self.assertRaisesRegexp(CloudifyClientError,
                                error_message,
                                self.client.agents.get,
                                'agent@')

    def test_get_nonexisting_agent(self):
        error_message = '404: Requested `Agent` with ID `agent_1` ' \
                        'was not found'
        self.assertRaisesRegexp(CloudifyClientError,
                                error_message,
                                self.client.agents.get,
                                'agent_1')

    def test_create_agent(self):
        put_node_instance(self.sm,
                          instance_id='node_instance_1',
                          deployment_id='deployment_1',
                          runtime_properties={'key': 'value'})
        self.client.agents.create('agent_1',
                                  'node_instance_1',
                                  **self.agent_data)
        agent = self.sm.get(Agent, 'agent_1')
        self.assertEqual(agent.name, 'agent_1')
        self.assertEqual(agent.node_instance_id, 'node_instance_1')
        self.assertEqual(agent.visibility, 'tenant')
        self.assertEqual(agent.node_id, 'node_id')
        self.assertEqual(agent.creator.username, 'admin')

    def test_create_invalid_agent_name(self):
        error_message = '400: The `name` argument contains illegal characters'
        self.assertRaisesRegexp(CloudifyClientError,
                                error_message,
                                self.client.agents.create,
                                'agent@',
                                'node_instance_1')

    def test_create_agent_already_exists(self):
        self._get_or_create_node_instance()
        self.client.agents.create('agent_1',
                                  'node_instance_1',
                                  **self.agent_data)
        none_response = self.client.agents.create('agent_1',
                                                  'node_instance_1',
                                                  **self.agent_data)
        self.assertEqual(none_response.name, None)
        self.assertEqual(none_response.state, None)

    def test_create_agent_invalid_node_instance(self):
        error_message = '404: Requested `NodeInstance` with ID ' \
                        '`node_instance_2` was not found'
        self.assertRaisesRegexp(CloudifyClientError,
                                error_message,
                                self.client.agents.create,
                                'agent_1',
                                'node_instance_2')

    def test_update_agent(self):
        self.put_agent()
        self.client.agents.update('agent_1', AgentState.STARTED)
        agent = self.client.agents.get('agent_1')
        self.assertEqual(agent.name, 'agent_1')
        self.assertEqual(agent.state, AgentState.STARTED)

    def test_update_without_state(self):
        self.put_agent()
        response = self.patch('/agents/agent_1', {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['message'],
                         'Missing state in json request body')

    def test_update_invalid_state(self):
        self.put_agent()
        error_message = '400: Invalid agent state: `test_state`'
        self.assertRaisesRegexp(CloudifyClientError,
                                error_message,
                                self.client.agents.update,
                                'agent_1',
                                'test_state')

    def test_agent_deleted_following_instance_deletion(self):
        self.put_agent()
        agent = self.client.agents.get('agent_1')
        self.assertEqual('agent_1', agent.name)
        self.assertEqual('node_instance_1', agent.node_instance_id)
        node_instance = self.sm.get(NodeInstance, 'node_instance_1')
        self.sm.delete(node_instance)
        error_message = '404: Requested `Agent` with ID `agent_1` ' \
                        'was not found'
        self.assertRaisesRegexp(CloudifyClientError,
                                error_message,
                                self.client.agents.get,
                                'agent_1')

    def test_instance_exist_after_deleting_agent(self):
        self.put_agent()
        agent = self.sm.get(Agent, 'agent_1')
        self.sm.delete(agent)
        node_instance = self.sm.get(NodeInstance, 'node_instance_1')
        self.assertEqual(node_instance.id, 'node_instance_1')
        self.assertEqual(node_instance.deployment_id, 'deployment_1')

    def put_agent(self,
                  agent_name='agent_1',
                  instance_id='node_instance_1',
                  deployment_id='deployment_1'):
        node_instance = self._get_or_create_node_instance(instance_id,
                                                          deployment_id)
        agent = Agent(
            id=agent_name,
            name=agent_name,
            ip='127.0.0.1',
            install_method='remote',
            system='centos core',
            version='4.5.5',
            visibility='tenant',
            state=AgentState.CREATING,
            rabbitmq_username='rabbitmq_user_{0}'.format(agent_name),
            rabbitmq_password=encrypt(generate_user_password()),
            rabbitmq_exchange=agent_name,
            created_at=get_formatted_timestamp(),
            updated_at=get_formatted_timestamp()
        )
        agent.node_instance = node_instance
        return self.sm.put(agent)

    def _get_or_create_node_instance(self,
                                     instance_id='node_instance_1',
                                     deployment_id='deployment_1'):
        try:
            return self.sm.get(NodeInstance, instance_id)
        except manager_exceptions.NotFoundError:
            return put_node_instance(self.sm,
                                     instance_id=instance_id,
                                     deployment_id=deployment_id,
                                     runtime_properties={'key': 'value'})

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

import time
from nose.plugins.attrib import attr
from manager_rest.test import base_test


@attr(client_min_version=2, client_max_version=base_test.LATEST_API_VERSION)
class AgentsTest(base_test.BaseServerTestCase):

    def test_agents(self):
        self.put_deployment(
            deployment_id='deployment',
            blueprint_file_name='blueprint.yaml',
            blueprint_id='blueprint')
        self.put_deployment(
            deployment_id='deployment2',
            blueprint_file_name='blueprint.yaml',
            blueprint_id='blueprint2')
        vm = self.client.node_instances.list(deployment_id='deployment',
                                             node_id='vm')[0]
        timestamp = str(time.time())
        runtime_properties = {
            'agent_status': {
                'agent_alive_crossbroker': True,
                'agent_alive': True,
                'timestamp': timestamp
            }
        }
        self.client.node_instances.update(
            node_instance_id=vm.id,
            runtime_properties=runtime_properties
        )
        response = self.get('/agents')
        agents = response.json
        for agent in agents:
            self.assertEqual(agent['node_id'], 'vm')
            if agent['id'] == vm.id:
                self.assertTrue(agent['validated'])
                self.assertTrue(agent['alive'])
                self.assertTrue(agent['installable'])
                self.assertEquals(agent['last_validation_timestamp'],
                                  timestamp)
            else:
                self.assertFalse(agent['validated'])
        response = self.get('/agents', query_params={
            'deployment_id': 'deployment'})
        agents = response.json
        self.assertEquals(1, len(agents))
        self.assertEquals(agents[0]['id'], vm.id)

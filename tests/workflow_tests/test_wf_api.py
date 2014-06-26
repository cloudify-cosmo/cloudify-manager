########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'dank'

from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_and_execute_workflow as deploy
from testenv import send_task
from plugins.testmockoperations.tasks import get_mock_operation_invocations


class WorkflowsAPITest(TestCase):

    def test(self):
        parameters = {
            'key': 'key1',
            'value': 'value1'
        }
        result_dict = {'key1': 'value1'}
        deployment, _ = deploy(resource('dsl/workflow_api.yaml'),
                               'custom1',
                               parameters=parameters)

        # testing workflow remote task
        invocation = send_task(get_mock_operation_invocations).get()[0]
        self.assertDictEqual(result_dict, invocation)

        # testing workflow local task
        instance = self.client.node_instances.list(
            deployment_id=deployment.id)[0]
        # I am in love with eventual consistency
        instance = self.client.node_instances.get(instance.id)
        self.assertEqual('test_state', instance.state)
        self.assertDictEqual(result_dict, instance.runtime_properties)

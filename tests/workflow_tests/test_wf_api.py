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
from plugins.testmockoperations.tasks import (get_mock_operation_invocations,
                                              get_fail_invocations)

from testenv import delete_provider_context, restore_provider_context


class WorkflowsAPITest(TestCase):

    def setUp(self):
        super(WorkflowsAPITest, self).setUp()
        delete_provider_context()
        context = {'cloudify': {'workflows': {
            'task_retries': 2,
            'task_retry_interval': 1
        }}}
        self.client.manager.create_context(self._testMethodName, context)
        self.addCleanup(restore_provider_context)

    def test_simple(self):
        parameters = {
            'key': 'key1',
            'value': 'value1'
        }
        result_dict = {
            'key1': 'value1'
        }
        deployment, _ = deploy(resource('dsl/workflow_api.yaml'),
                               self._testMethodName,
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

    def test_fail_remote_task_eventual_success(self):
        deploy(resource('dsl/workflow_api.yaml'), self._testMethodName)

        # testing workflow remote task
        invocations = send_task(get_fail_invocations).get()
        self.assertEqual(3, len(invocations))
        for i in range(len(invocations) - 1):
            self.assertLessEqual(1, invocations[i+1] - invocations[i])

    def test_fail_remote_task_eventual_failure(self):
        self.assertRaises(RuntimeError, deploy,
                          resource('dsl/workflow_api.yaml'),
                          self._testMethodName)

        # testing workflow remote task
        invocations = send_task(get_fail_invocations).get()
        self.assertEqual(3, len(invocations))
        for i in range(len(invocations) - 1):
            self.assertLessEqual(1, invocations[i+1] - invocations[i])

    def test_fail_local_task_eventual_success(self):
        deploy(resource('dsl/workflow_api.yaml'), self._testMethodName)

    def test_fail_local_task_eventual_failure(self):
        deploy(resource('dsl/workflow_api.yaml'), self._testMethodName)
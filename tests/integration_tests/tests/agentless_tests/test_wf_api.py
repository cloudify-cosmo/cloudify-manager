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

import uuid
import pytest

from cloudify_rest_client.executions import Execution

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_workflows


@pytest.mark.usefixtures('mock_workflows_plugin')
@pytest.mark.usefixtures('testmockoperations_plugin')
class WorkflowsAPITest(AgentlessTestCase):

    def setUp(self):
        super(WorkflowsAPITest, self).setUp()
        self.do_get = True
        self.configure(retries=2, interval=1)

    def configure(self, retries, interval):
        self.client.manager.put_config('task_retries', retries)
        self.client.manager.put_config('task_retry_interval', interval)

    def test_simple(self):
        parameters = {
            'do_get': self.do_get,
            'key': 'key1',
            'value': 'value1'
        }
        result_dict = {
            'key1': 'value1'
        }
        deployment, _ = self.deploy_and_execute_workflow(
                resource('dsl/workflow_api.yaml'),
                self._testMethodName,
                parameters=parameters)

        # testing workflow remote task
        invocation = self.get_runtime_property(deployment.id,
                                               'mock_operation_invocation')[0]
        self.assertDictEqual(result_dict, invocation[0])

        # testing workflow local task
        instance = self.client.node_instances.list(
            deployment_id=deployment.id)[0]
        self.assertEqual('test_state', instance.state)

    def test_fail_remote_task_eventual_success(self):
        deployment, _ = self.deploy_and_execute_workflow(
                resource('dsl/workflow_api.yaml'),
                self._testMethodName,
                parameters={'do_get': self.do_get})

        # testing workflow remote task
        invocations = self.get_runtime_property(deployment.id,
                                                'failure_invocation')[0]
        self.assertEqual(3, len(invocations))
        for i in range(len(invocations) - 1):
            self.assertLessEqual(1, invocations[i+1] - invocations[i])

    def test_fail_remote_task_eventual_failure(self):
        deployment_id = 'd{0}'.format(uuid.uuid4())
        self.assertRaises(RuntimeError, self.deploy_and_execute_workflow,
                          resource('dsl/workflow_api.yaml'),
                          self._testMethodName,
                          deployment_id=deployment_id,
                          parameters={'do_get': self.do_get})

        # testing workflow remote task
        invocations = self.get_runtime_property(deployment_id,
                                                'failure_invocation')[0]
        self.assertEqual(3, len(invocations))
        for i in range(len(invocations) - 1):
            self.assertLessEqual(1, invocations[i+1] - invocations[i])

    def test_fail_local_task_eventual_success(self):
        self.deploy_and_execute_workflow(
            resource('dsl/workflow_api.yaml'), self._testMethodName,
            parameters={'do_get': self.do_get})

    def test_fail_local_task_eventual_failure(self):
        self._local_task_fail_impl(self._testMethodName)

    def test_fail_local_task_on_nonrecoverable_error(self):
        if not self.do_get:
            # setting infinite retries to make sure that the runtime error
            # raised is not because we ran out of retries
            # (no need to do this when self.do_get because the workflow will
            #  ensure that only one try was attempted)
            self.configure(retries=-1, interval=1)
        self._local_task_fail_impl(self._testMethodName)

    def _local_task_fail_impl(self, wf_name):
        if self.do_get:
            self.deploy_and_execute_workflow(
                resource('dsl/workflow_api.yaml'), wf_name,
                parameters={'do_get': self.do_get})
        else:
            self.assertRaises(RuntimeError,
                              self.deploy_and_execute_workflow,
                              resource('dsl/workflow_api.yaml'),
                              wf_name,
                              parameters={'do_get': self.do_get})

    def test_cancel_on_wait_for_task_termination(self):
        _, eid = self.deploy_and_execute_workflow(
            resource('dsl/workflow_api.yaml'), self._testMethodName,
            parameters={'do_get': self.do_get}, wait_for_execution=False)
        self.wait_for_execution_status(eid, status=Execution.STARTED)
        self.client.executions.cancel(eid)
        self.wait_for_execution_status(eid, status=Execution.CANCELLED)

    def test_cancel_on_task_retry_interval(self):
        self.configure(retries=2, interval=1000000)
        _, eid = self.deploy_and_execute_workflow(
            resource('dsl/workflow_api.yaml'), self._testMethodName,
            parameters={'do_get': self.do_get}, wait_for_execution=False)
        self.wait_for_execution_status(eid, status=Execution.STARTED)
        self.client.executions.cancel(eid)
        self.wait_for_execution_status(eid, status=Execution.CANCELLED)

    def test_illegal_non_graph_to_graph_mode(self):
        if not self.do_get:
            # no need to run twice
            return
        self.assertRaises(RuntimeError, self.deploy_and_execute_workflow,
                          resource('dsl/workflow_api.yaml'),
                          self._testMethodName)

    def test_workflow_deployment_scaling_groups(self):
        deployment, _ = self.deploy_and_execute_workflow(
            resource('dsl/store-scaling-groups.yaml'),
            workflow_name='workflow')
        instance = self.client.node_instances.list(
            deployment_id=deployment.id
        )[0]
        self.assertEqual(
            ['node'],
            instance.runtime_properties['scaling_groups']['group1']['members'])


class WorkflowsAPITestNoGet(WorkflowsAPITest):

    def setUp(self):
        super(WorkflowsAPITestNoGet, self).setUp()
        self.do_get = False

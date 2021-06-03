########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

INFINITY = -1
pytestmark = pytest.mark.group_workflows


@pytest.mark.usefixtures('testmockoperations_plugin')
class TaskRetriesTest(AgentlessTestCase):

    def setUp(self):
        super(TaskRetriesTest, self).setUp()
        self.events = []

    def configure(self, retries, retry_interval):
        self.client.manager.put_config('task_retries', retries)
        self.client.manager.put_config('subgraph_retries', 0)
        self.client.manager.put_config('task_retry_interval', retry_interval)

    def test_retries_and_retry_interval(self):
        self._test_retries_and_retry_interval_impl(
            blueprint='dsl/workflow_task_retries_1.yaml',
            retries=2,
            retry_interval=3,
            expected_interval=3,
            expected_retries=2,
            invocations_type='failure_invocation')

    def test_infinite_retries(self):
        self._test_retries_and_retry_interval_impl(
            blueprint='dsl/workflow_task_retries_2.yaml',
            retries=INFINITY,
            retry_interval=1,
            expected_interval=1,
            # see blueprint
            expected_retries=5,
            invocations_type='failure_invocation')

    def test_retries_ignore_total(self):
        self._test_retries_and_retry_interval_impl(
            blueprint='dsl/workflow_task_retries_3.yaml',
            retries=0,
            retry_interval=0,
            expected_interval=0,
            # see blueprint (get_state does ignores total_retries)
            expected_retries=3,
            invocations_type='host_get_state_invocation')

    def test_non_recoverable_error(self):
        self._test_retries_and_retry_interval_impl(
            blueprint='dsl/workflow_task_retries_4.yaml',
            retries=-1,
            retry_interval=1,
            expected_interval=1,
            expected_retries=0,
            invocations_type='failure_invocation',
            expect_failure=True)

    def test_recoverable_error(self):
        self._test_retries_and_retry_interval_impl(
            blueprint='dsl/workflow_task_retries_5.yaml',
            retries=1,
            retry_interval=1000,
            # blueprint overrides retry_interval
            expected_interval=1,
            expected_retries=1,
            invocations_type='failure_invocation')

    def test_operation_retry_in_operation_mapping(self):
        self._test_retries_and_retry_interval_impl(
            blueprint='dsl/workflow_task_retries_6.yaml',
            # setting global values to something really big
            retries=1000,
            retry_interval=1000,
            # blueprint operation mapping overrides retry_interval
            # and retries
            expected_interval=1,
            expected_retries=2,
            invocations_type='failure_invocation')

    def test_operation_retry(self):
        self.configure(retries=5, retry_interval=5)
        deployment_id = 'd{0}'.format(uuid.uuid4())
        self.deploy_application(
            resource('dsl/test-operation-retry-blueprint.yaml'),
            deployment_id=deployment_id)
        invocations = self.get_runtime_property(deployment_id,
                                                'retry_invocations')[0]
        self.assertEqual(4, invocations)

        # 1 asserting event messages reflect that the task has been rescheduled
        # 2 asserting that task events contain current_retries/total_retries
        #   only asserting that the properties exists and nothing logical
        #   because this is already covered in the local workflow tests
        def assertion():
            events = self.client.events.list(deployment_id=deployment_id,
                                             include_logs=True)
            self.assertGreater(len(events), 0)
            self.assertTrue(any(
                'Task rescheduled' in event['message']
                for event in events))
            self.assertTrue(any(
                'Retrying operation' in event['message']
                for event in events))

            # We're looking only at the events from the create operation
            retry_events = [
                event
                for event in events
                if event['operation'] == 'cloudify.interfaces.lifecycle.create'
            ]

            # Note: sorting by timestamp and event_type to guarantee
            # that tasks will be correctly ordered
            # even if they have the same timestamp
            event_type_sort_order = {
                'sending_task': 0,
                'task_started': 1,
                'task_rescheduled': 2,
                'task_succeeded': 3
            }
            retry_events = [e for e in retry_events if 'event_type' in e]
            retry_events = sorted(
                retry_events,
                key=lambda e: (
                    e['timestamp'],
                    event_type_sort_order[e['event_type']],
                ),
            )
            self.assertEqual([e['event_type'] for e in retry_events],
                             ['sending_task', 'task_rescheduled'] * 3 +
                             ['sending_task', 'task_succeeded'])

            self.assertTrue(retry_events[2]['message'].endswith('[retry 1/5]'))
            self.assertTrue(retry_events[3]['message'].endswith('[retry 1/5]'))
            self.assertTrue(retry_events[4]['message'].endswith('[retry 2/5]'))
            self.assertTrue(retry_events[5]['message'].endswith('[retry 2/5]'))
            self.assertTrue(retry_events[6]['message'].endswith('[retry 3/5]'))
            self.assertTrue(retry_events[7]['message'].endswith('[retry 3/5]'))

        # events are async so we may have to wait some
        self.do_assertions(assertion, timeout=10)

    def _test_retries_and_retry_interval_impl(self,
                                              blueprint,
                                              retries,
                                              retry_interval,
                                              expected_interval,
                                              expected_retries,
                                              invocations_type,
                                              expect_failure=False):
        self.configure(retries=retries, retry_interval=retry_interval)
        deployment_id = 'd{0}'.format(uuid.uuid4())
        if expect_failure:
            self.assertRaises(RuntimeError, self.deploy_application,
                              dsl_path=resource(blueprint),
                              deployment_id=deployment_id)
        else:
            self.deploy_application(
                resource(blueprint),
                deployment_id=deployment_id)
        invocations = self.get_runtime_property(deployment_id,
                                                invocations_type)[0]
        self.assertEqual(expected_retries + 1, len(invocations))
        for i in range(len(invocations) - 1):
            self.assertLessEqual(expected_interval,
                                 invocations[i + 1] - invocations[i])

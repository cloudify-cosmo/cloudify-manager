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

from testenv import TestCase, ProcessModeTestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import delete_provider_context
from testenv.utils import restore_provider_context

INFINITY = -1


class TaskRetriesTest(TestCase):

    def setUp(self):
        super(TaskRetriesTest, self).setUp()
        delete_provider_context()
        self.addCleanup(restore_provider_context)

    def configure(self, retries, retry_interval):
        context = {'cloudify': {'workflows': {
            'task_retries': retries,
            'task_retry_interval': retry_interval
        }}}
        self.client.manager.create_context(self._testMethodName, context)

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

    def _test_retries_and_retry_interval_impl(self,
                                              blueprint,
                                              retries,
                                              retry_interval,
                                              expected_interval,
                                              expected_retries,
                                              invocations_type,
                                              expect_failure=False):
        self.configure(retries=retries, retry_interval=retry_interval)
        deployment_id = str(uuid.uuid4())
        if expect_failure:
            self.assertRaises(RuntimeError, deploy,
                              dsl_path=resource(blueprint),
                              deployment_id=deployment_id)
        else:
            deploy(resource(blueprint),
                   deployment_id=deployment_id)
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )[invocations_type]
        self.assertEqual(expected_retries + 1, len(invocations))
        for i in range(len(invocations) - 1):
            self.assertLessEqual(expected_interval,
                                 invocations[i+1] - invocations[i])


class ProcessModeTaskRetriesTest(ProcessModeTestCase):

    def setUp(self):
        super(ProcessModeTaskRetriesTest, self).setUp()
        delete_provider_context()
        self.addCleanup(restore_provider_context)

    def configure(self, retries, retry_interval):
        context = {'cloudify': {'workflows': {
            'task_retries': retries,
            'task_retry_interval': retry_interval
        }}}
        self.client.manager.create_context(self._testMethodName, context)

    def _test_retries_and_retry_interval_impl(self,
                                              blueprint,
                                              retries,
                                              retry_interval,
                                              expected_interval,
                                              expected_retries,
                                              invocations_type,
                                              expect_failure=False,
                                              inputs=None):
        self.configure(retries=retries, retry_interval=retry_interval)
        deployment_id = str(uuid.uuid4())
        if expect_failure:
            self.assertRaises(RuntimeError, deploy,
                              dsl_path=resource(blueprint),
                              deployment_id=deployment_id,
                              inputs=inputs)
        else:
            deploy(resource(blueprint),
                   deployment_id=deployment_id,
                   inputs=inputs)
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )[invocations_type]
        self.assertEqual(expected_retries + 1, len(invocations))
        for i in range(len(invocations) - 1):
            self.assertLessEqual(expected_interval,
                                 invocations[i+1] - invocations[i])

    def test_user_exception(self):
        self._test_retries_and_retry_interval_impl(
            blueprint='dsl/user_exception.yaml',
            retries=1,
            retry_interval=5,
            expected_interval=5,
            expected_retries=1,
            invocations_type='failure_invocation',
            expect_failure=True,
            inputs={
                'exception_type': 'user_exception'
            })

    def test_user_exception_non_recoverable(self):
        self._test_retries_and_retry_interval_impl(
            blueprint='dsl/user_exception.yaml',
            retries=1,
            retry_interval=5,
            expected_interval=5,
            # non recoverable exception
            # should be retried
            expected_retries=0,
            invocations_type='failure_invocation',
            expect_failure=True,
            inputs={
                'exception_type': 'user_exception_non_recoverable'
            })

    def test_user_exception_recoverable(self):
        self._test_retries_and_retry_interval_impl(
            blueprint='dsl/user_exception.yaml',
            retries=1,
            retry_interval=5,
            expected_interval=5,
            expected_retries=1,
            invocations_type='failure_invocation',
            expect_failure=True,
            inputs={
                'exception_type': 'user_exception_recoverable'
            })

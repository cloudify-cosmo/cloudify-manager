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

__author__ = 'idanmo'


from testenv import TestCase
from testenv import get_resource as resource, deploy_application as deploy
from testenv import delete_provider_context, restore_provider_context
from testenv import send_task

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
        retries = 2
        retry_interval = 3
        self.configure(retries=2, retry_interval=3)
        deploy(resource("dsl/workflow_task_retries_1.yaml"))
        from plugins.testmockoperations.tasks import get_fail_invocations
        invocations = send_task(get_fail_invocations).get()
        self.assertEqual(retries + 1, len(invocations))
        for i in range(len(invocations) - 1):
            self.assertLessEqual(retry_interval,
                                 invocations[i+1] - invocations[i])

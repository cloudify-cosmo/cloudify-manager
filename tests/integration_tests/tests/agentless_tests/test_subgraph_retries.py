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

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource
from integration_tests.tests import utils as test_utils


class TaskRetriesTest(AgentlessTestCase):

    def setUp(self):
        super(TaskRetriesTest, self).setUp()
        test_utils.delete_provider_context()

    def test_subgraph_retries_provider_config_config(self):
        context = {'cloudify': {'workflows': {
            'task_retries': 0,
            'task_retry_interval': 0,
            'subgraph_retries': 2
        }}}
        deployment_id = str(uuid.uuid4())
        self.client.manager.create_context(self._testMethodName, context)
        self.deploy_application(
            resource('dsl/workflow_subgraph_retries.yaml'),
            deployment_id=deployment_id)
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )['failure_invocation']
        self.assertEqual(len(invocations), 3)

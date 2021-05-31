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

pytestmark = pytest.mark.group_workflows


@pytest.mark.usefixtures('testmockoperations_plugin')
class TaskRetriesTest(AgentlessTestCase):
    def test_subgraph_retries_config(self):
        self.client.manager.put_config('task_retries', 0)
        self.client.manager.put_config('task_retry_interval', 0)
        self.client.manager.put_config('subgraph_retries', 2)
        deployment_id = 'd{0}'.format(uuid.uuid4())
        self.deploy_application(
            resource('dsl/workflow_subgraph_retries.yaml'),
            deployment_id=deployment_id)
        invocations = self.get_runtime_property(deployment_id,
                                                'failure_invocation')[0]
        self.assertEqual(len(invocations), 3)

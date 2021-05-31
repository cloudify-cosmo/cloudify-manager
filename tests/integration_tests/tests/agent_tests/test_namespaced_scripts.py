#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

import uuid
import pytest

from integration_tests import AgentTestCase
from integration_tests.tests.utils import get_resource as resource
from integration_tests.tests.utils import wait_for_blueprint_upload

pytestmark = pytest.mark.group_dsl


class NamespacedScriptsTest(AgentTestCase):
    def test_success_deploy_namespaced_blueprint_with_scripts(self):
        basic_blueprint_path =\
            resource('dsl/agent_tests/blueprint_with_scripts.yaml')
        blueprint_id = 'imported_scripts'
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id=blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client)
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource(
            'dsl/agent_tests/blueprints/'
            'blueprint_with_namespaced_blueprint_import.yaml')
        _, execution_id = self.deploy_application(dsl_path,
                                                  deployment_id=deployment_id)

        events = self.client.events.list(execution_id=execution_id,
                                         sort='timestamp')
        script_success_msg = "Task succeeded 'script_runner.tasks.run'"
        script_success_events = [event['message'] for event in events
                                 if script_success_msg == event['message']]
        self.assertEqual(len(script_success_events), 1)
        agent_success_msg = 'Agent created'
        agent_success_events = [event['message'] for event in events
                                if agent_success_msg == event['message']]
        self.assertEqual(len(agent_success_events), 1)

    def test_success_deploy_namespaced_blueprint_with_local_scripts(self):
        deployment_id = 'dep'
        dsl_path = resource(
            'dsl/agent_tests/'
            'blueprint_with_namespaced_local_blueprint_import.yaml')
        _, execution_id = self.deploy_application(dsl_path,
                                                  deployment_id=deployment_id)

        events = self.client.events.list(execution_id=execution_id,
                                         sort='timestamp')
        script_success_msg = "Task succeeded 'script_runner.tasks.run'"
        script_success_events = [event['message'] for event in events
                                 if script_success_msg == event['message']]
        self.assertEqual(len(script_success_events), 1)
        agent_success_msg = 'Agent created'
        agent_success_events = [event['message'] for event in events
                                if agent_success_msg == event['message']]
        self.assertEqual(len(agent_success_events), 1)

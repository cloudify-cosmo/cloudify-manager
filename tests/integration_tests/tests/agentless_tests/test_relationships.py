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

import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_dsl


@pytest.mark.usefixtures('cloudmock_plugin')
@pytest.mark.usefixtures('testmockoperations_plugin')
class TestRelationships(AgentlessTestCase):

    def test_pre_source_started_location_source(self):
        dsl_path = resource(
            "dsl/relationship_interface_pre_source_location_source.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        self.verify_assertions(deployment.id,
                               hook='pre-init',
                               runs_on_source=True)

    def test_post_source_started_location_target(self):
        dsl_path = resource(
            "dsl/relationship_interface_post_source_location_target.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        self.verify_assertions(deployment.id,
                               hook='post-init',
                               runs_on_source=False)

    def verify_assertions(self, deployment_id, hook, runs_on_source):

        source_node_id_prefix = 'mock_node_that_connects_to_host'
        target_node_id_prefix = 'host'

        machines = self.get_runtime_property(deployment_id, 'machines')[0]
        self.assertEqual(1, len(machines))

        state = self.get_runtime_property(deployment_id, 'connection_state')[0]
        source_id = state['source_id']
        target_id = state['target_id']

        self.assertTrue(source_id.startswith(source_node_id_prefix))
        self.assertTrue(target_id.startswith(target_node_id_prefix))

        self.assertTrue(self.is_node_started(target_id))

        self.assertEqual('source_property_value',
                         state['source_properties']['source_property_key'])
        self.assertEqual(
            'target_property_value',
            state['target_properties']['target_property_key'])
        self.assertEqual(
            'source_runtime_property_value',
            state['source_runtime_properties']['source_runtime_property_key']
        )
        self.assertEqual(
            'target_runtime_property_value',
            state['target_runtime_properties']
                 ['target_runtime_property_key']
        )

        if hook == 'post-init':
            self.assertTrue(self.is_node_started(source_id))
        elif hook != 'pre-init':
            self.fail('unhandled state')

        connector_timestamp = state['time']
        reachable_timestamp = \
            self.get_runtime_property(deployment_id, 'time')[0]
        touched_timestamp = \
            self.get_runtime_property(deployment_id, 'touched_time')[0]

        if hook == 'pre-init':
            self.assertLess(touched_timestamp, connector_timestamp)
            self.assertGreater(reachable_timestamp, connector_timestamp)
        elif hook == 'post-init':
            self.assertLess(reachable_timestamp, connector_timestamp)
        else:
            self.fail('unhandled state')

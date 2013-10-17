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
from testenv import deploy_application as deploy


class TestRelationships(TestCase):

    def test_pre_source_started_location_source(self):
        dsl_path = resource("dsl/relationship-interface-pre-source-location-source.yaml")
        deploy(dsl_path)
        self.verify_assertions(pre_started=True,
                               runs_on_source=True)

    def test_post_source_started_location_target(self):
        dsl_path = resource("dsl/relationship-interface-post-source-location-target.yaml")
        deploy(dsl_path)
        self.verify_assertions(pre_started=False,
                               runs_on_source=False)

    def verify_assertions(self, pre_started, runs_on_source):

        source_id = 'simple_web_server.mock_node_that_connects_to_host'
        target_id = 'simple_web_server.host'

        from cosmo.cloudmock.tasks import get_machines
        result = get_machines.apply_async()
        machines = result.get(timeout=10)
        self.assertEquals(1, len(machines))

        from cosmo.connection_configurer_mock.tasks import get_state as config_get_state
        result = config_get_state.apply_async()
        state = result.get(timeout=10)

        self.assertEquals(target_id, state['target_id'])
        self.assertEquals(source_id, state['source_id'])
        self.assertEquals('true', state['source_properties']['cloudify_runtime'][target_id]['reachable'])
        self.assertEquals('source_property_value', state['source_properties']['source_property_key'])
        self.assertEquals('target_property_value', state['target_properties']['target_property_key'])
        if pre_started:
            self.assertTrue(source_id not in state['source_properties']['cloudify_runtime'])
            self.assertTrue(source_id not in state['target_properties']['cloudify_runtime'])
        else:
            self.assertEquals('true', state['source_properties']['cloudify_runtime'][source_id]['reachable'])

        # TODO: test that run_on_node attribute is respected
        # if runs_on_source:
        #     self.assertEquals(source_id, state['id'])
        #     self.assertEquals(target_id, state['relationship_id'])
        # else:
        #     self.assertEquals(target_id, state['id'])
        #     self.assertEquals(source_id, state['relationship_id'])

        connector_timestamp = state['time']

        from cosmo.testmockoperations.tasks import get_state as testmock_get_state
        result = testmock_get_state.apply_async()
        state = result.get(timeout=10)
        reachable_timestamp = state['time']
        if pre_started:
            self.assertGreater(reachable_timestamp, connector_timestamp)
        else:
            self.assertLess(reachable_timestamp, connector_timestamp)

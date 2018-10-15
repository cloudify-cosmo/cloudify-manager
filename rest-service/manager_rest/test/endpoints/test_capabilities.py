#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

from manager_rest.test import base_test
from manager_rest.test.attribute import attr

from cloudify_rest_client.exceptions import CloudifyClientError


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class CapabilitiesTestCase(base_test.BaseServerTestCase):

    complex_capability = {
        'level_1': {
            'level_2': {
                'key_1': 'value_3',
                'level_3': ['value_1', 'value_2']
            },
            'key_2': 'value_4'
        }
    }

    def _deploy(self, deployment_id, blueprint_name):
        self.put_deployment(
            blueprint_file_name=blueprint_name,
            blueprint_id=deployment_id,
            deployment_id=deployment_id)

    def test_capabilities_evaluation(self):
        deployment_id = 'shared'
        self._deploy(deployment_id, 'blueprint_with_capabilities.yaml')

        capabilities = self.client.deployments.capabilities.get(deployment_id)

        self.assertEqual(capabilities['deployment_id'], deployment_id)

        capabilities = capabilities['capabilities']

        self.assertEqual(capabilities['node_1_key'], 'default_value')
        self.assertEqual(capabilities['node_2_key'], 'override_value')
        self.assertDictEqual(
            capabilities['complex_capability'],
            self.complex_capability
        )

    def test_get_capability(self):
        shared_dep_id = 'shared'
        other_dep_id = 'other_dep_id'
        self._deploy(shared_dep_id, 'blueprint_with_capabilities.yaml')
        self._deploy(other_dep_id, 'blueprint_with_get_capability.yaml')

        values_mapping = {
            'node1': {'get_capability': ['shared', 'node_1_key']},
            'node2': {'get_capability': ['shared', 'node_2_key']}
        }

        evaluated_values_mapping = {
            'node1': 'default_value',
            'node2': 'override_value'
        }

        # Node properties are not evaluated by default, so we expect to see
        # the actual intrinsic function dict here
        nodes = self.client.nodes.list(deployment_id=other_dep_id)
        for node in nodes:
            self.assertEqual(
                node.properties['key'],
                values_mapping[node.id]
            )

        # Node properties are not evaluated by default, so we expect to see
        # the actual intrinsic function dict here
        nodes = self.client.nodes.list(
            deployment_id=other_dep_id,
            evaluate_functions=True
        )
        for node in nodes:
            self.assertEqual(
                node.properties['key'],
                evaluated_values_mapping[node.id]
            )

        # Outputs are always evaluated, so it's safe to compare
        outputs = self.client.deployments.outputs.get(other_dep_id)['outputs']
        self.assertDictEqual(
            outputs['complex_output'],
            self.complex_capability
        )

    def test_chain_get_capability(self):
        chain_1 = 'chain_1'
        chain_2 = 'chain_2'
        chain_3 = 'chain_3'

        self._deploy(chain_1, 'capability_chain_1.yaml')
        self._deploy(chain_2, 'capability_chain_2.yaml')
        self._deploy(chain_3, 'capability_chain_3.yaml')

        outputs = self.client.deployments.outputs.get(chain_3)['outputs']
        self.assertEqual(outputs['chain_3_output'], 'initial_value')

    def test_non_existent_deployment(self):
        dep_id = 'dep_id'
        self._deploy(dep_id, 'blueprint_with_non_existent_deployment.yaml')

        # Trying to evaluate functions on the node's properties will trigger
        # `get_capability` evaluation, which should fail
        self.assertRaisesRegexp(
            CloudifyClientError,
            'Requested `Deployment` with ID `wrong_id` was not found',
            self.client.nodes.get,
            deployment_id=dep_id,
            node_id='node1',
            evaluate_functions=True
        )

    def test_non_existent_capability(self):
        deployment_id = 'shared'
        other_dep_id = 'other_dep_id'
        self._deploy(deployment_id, 'blueprint_with_capabilities.yaml')
        self._deploy(other_dep_id,
                     'blueprint_with_non_existent_capability.yaml')

        # Trying to evaluate functions on the node's properties will trigger
        # `get_capability` evaluation, which should fail
        self.assertRaisesRegexp(
            CloudifyClientError,
            'Requested capability `wrong_capability` is not '
            'declared in deployment `other_dep_id`',
            self.client.nodes.get,
            deployment_id=other_dep_id,
            node_id='node1',
            evaluate_functions=True
        )

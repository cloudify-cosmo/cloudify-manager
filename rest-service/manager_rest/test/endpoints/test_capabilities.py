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

from typing import Dict, Any

from manager_rest.storage import models
from manager_rest.test import base_test
from manager_rest.test.utils import node_intance_counts

from cloudify_rest_client.exceptions import CloudifyClientError


class CapabilitiesTestCase(base_test.BaseServerTestCase):

    complex_capability: Dict[str, Any] = {
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
        self.assertListEqual(
            capabilities['node_1_key_nested'],
            [{'nested': 'default_value'}])
        self.assertListEqual(
            capabilities['node_2_key_nested'],
            [{'nested': 'override_value'}])
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
            'node2': {'get_capability': ['shared', 'node_2_key']},
            'node1_nested':
                {
                    'get_capability':
                        ['shared', 'node_1_key_nested', 0, 'nested']},
            'node2_nested':
                {
                    'get_capability':
                        ['shared', 'node_2_key_nested', 0, 'nested']}
        }

        evaluated_values_mapping = {
            'node1': 'default_value',
            'node2': 'override_value',
            'node1_nested': 'default_value',
            'node2_nested': 'override_value'
        }

        # Node properties are not evaluated by default, so we expect to see
        # the actual intrinsic function dict here
        nodes = self.client.nodes.list(deployment_id=other_dep_id)
        for node in nodes:
            self.assertEqual(
                node.properties['key'],
                values_mapping[node.id]
            )
            self.assertEqual(
                node.properties['key_nested'],
                values_mapping[node.id + '_nested']
            )

        # We're passing evaluate_functions=True, so we expect to see the
        # evaluated values here
        nodes = self.client.nodes.list(
            deployment_id=other_dep_id,
            evaluate_functions=True
        )
        for node in nodes:
            self.assertEqual(
                node.properties['key'],
                evaluated_values_mapping[node.id]
            )
            self.assertEqual(
                node.properties['key_nested'],
                evaluated_values_mapping[node.id + '_nested']
            )

        # Outputs are always evaluated, so it's safe to compare
        outputs = self.client.deployments.outputs.get(other_dep_id)['outputs']
        self.assertDictEqual(
            outputs['complex_output'],
            self.complex_capability
        )
        self.assertEqual(
            outputs['complex_output_nested'],
            self.complex_capability['level_1']['level_2']['level_3'][0]
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
        self.assertRaisesRegex(
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
        self.assertRaisesRegex(
            CloudifyClientError,
            'Requested capability `wrong_capability` is not '
            'declared in deployment `shared`',
            self.client.nodes.get,
            deployment_id=other_dep_id,
            node_id='node1',
            evaluate_functions=True
        )

    def test_non_existent_nested_attr_of_capability(self):
        deployment_id = 'shared'
        other_dep_id = 'other_dep_id'
        self._deploy(deployment_id, 'blueprint_with_capabilities.yaml')
        self._deploy(
            other_dep_id,
            'blueprint_with_non_existent_nested_attr_of_capability.yaml')

        # Trying to evaluate functions on the node's properties will trigger
        # `get_capability` evaluation, which should fail
        self.assertRaisesRegex(
            CloudifyClientError,
            "Attribute 'random_stuff' doesn't exist in 'complex_capability' "
            "in deployment 'shared'.",
            self.client.nodes.get,
            deployment_id=other_dep_id,
            node_id='node1',
            evaluate_functions=True
        )

    def test_non_existent_nested_index_of_capability(self):
        deployment_id = 'shared'
        other_dep_id = 'other_dep_id'
        self._deploy(deployment_id, 'blueprint_with_capabilities.yaml')
        self._deploy(
            other_dep_id,
            'blueprint_with_non_existent_nested_index_of_capability.yaml')

        # Trying to evaluate functions on the node's properties will trigger
        # `get_capability` evaluation, which should fail
        self.assertRaisesRegex(
            CloudifyClientError,
            "List size of 'complex_capability.level_1.level_2.level_3' is 2, "
            "in deployment 'shared', but index 8 is retrieved.",
            self.client.nodes.get,
            deployment_id=other_dep_id,
            node_id='node1',
            evaluate_functions=True
        )

    def test_nested_capability_bad_index_type(self):
        deployment_id = 'shared'
        other_dep_id = 'other_dep_id'
        self._deploy(deployment_id, 'blueprint_with_capabilities.yaml')
        self._deploy(
            other_dep_id,
            'blueprint_with_nested_capability_bad_index_type.yaml')

        # Trying to evaluate functions on the node's properties will trigger
        # `get_capability` evaluation, which should fail
        self.assertRaisesRegex(
            CloudifyClientError,
            "Item in index 5 in the get_capability arguments list "
            "\\[shared, complex_capability, level_1, level_2, "
            "level_3, bad_index_type\\] is expected to be an int but "
            "got (str|unicode).",
            self.client.nodes.get,
            deployment_id=other_dep_id,
            node_id='node1',
            evaluate_functions=True
        )

    def test_no_capabilities(self):
        deployment_id = 'deployment'
        self._deploy(deployment_id, 'blueprint.yaml')
        capabilities = self.client.deployments.capabilities.get('deployment')
        self.assertEqual(capabilities['capabilities'], {})


class TestGetGroupCapability(base_test.BaseServerTestCase):
    def test_get_capability(self):
        """Test the various variants of get_group_capability"""
        bp = models.Blueprint(id='bp', creator=self.user, tenant=self.tenant)

        # prepare a deployment-group with 3 deployments, each having
        # different capabilities
        for dep_id, capabilities in [
            ('dep1', {
                'cap1': {'value': 'd1-inp1'},
                'cap2': {'value': 'd1-inp2'},
                'complex_capability': {
                    'value': {'level_1': ['d1-inp1', 'd1-inp2']}
                }
            }),
            ('dep2', {
                'cap1': {'value': 'd2-inp1'},
                'cap2': {'value': 'd2-inp2'},
                'complex_capability': {
                    'value': {'level_1': ['d2-inp1', 'd2-inp2']}
                }
            }),
            ('dep3', {'cap1': {'value': 'd3-inp1'}}),
        ]:
            models.Deployment(
                id=dep_id,
                capabilities=capabilities,
                blueprint=bp, creator=self.user, tenant=self.tenant,
            )

        self.client.deployment_groups.put(
            'g1',
            deployment_ids=['dep1', 'dep2', 'dep3'],
        )

        # those are going to be the functions that we assert on. We'll test
        # both retrieving those values in deployment outputs, and in node
        # properties
        to_retrieve = {
            'cap1': {'get_group_capability': ['g1', 'cap1']},
            'cap2': {'get_group_capability': ['g1', 'cap2']},
            'both_caps': {'get_group_capability': ['g1', ['cap1', 'cap2']]},
            'cap1_by_id': {
                'get_group_capability': ['g1', 'deployment_id:cap1']
            },
            'complex_cap': {
                'get_group_capability': ['g1', 'complex_capability']
            },
            'complex_cap_indexed': {
                'get_group_capability': [
                    'g1', 'complex_capability', 'level_1', 1,
                ],
            },
            'complex_cap_indexed_by_id': {
                'get_group_capability': [
                    'g1', 'deployment_id:complex_capability', 'level_1', 1,
                ],
            },
        }

        dep5 = models.Deployment(
            id='dep5',
            outputs={k: {'value': v} for k, v in to_retrieve.items()},
            blueprint=bp, creator=self.user, tenant=self.tenant,
        )
        models.Node(
            id='node1',
            type='node',
            properties={'value': to_retrieve},
            deployment=dep5,
            creator=self.user,
            tenant=self.tenant,
            **node_intance_counts(1),
        )

        node_property = self.client.nodes.get(
            deployment_id=dep5.id,
            node_id='node1',
            evaluate_functions=True,
        ).properties['value']
        outputs = self.client.deployments.outputs.get(dep5.id)['outputs']

        assert outputs == node_property
        assert outputs['cap1'] == ['d1-inp1', 'd2-inp1', 'd3-inp1']
        assert outputs['cap2'] == ['d1-inp2', 'd2-inp2']
        assert outputs['both_caps'] == [
            ['d1-inp1', 'd1-inp2'],
            ['d2-inp1', 'd2-inp2'],
            ['d3-inp1', None],
        ]
        assert outputs['cap1_by_id'] == {
            'dep1': 'd1-inp1',
            'dep2': 'd2-inp1',
            'dep3': 'd3-inp1',
        }
        assert outputs['complex_cap'] == [
            {'level_1': ['d1-inp1', 'd1-inp2']},
            {'level_1': ['d2-inp1', 'd2-inp2']},
        ]
        assert outputs['complex_cap_indexed'] == ['d1-inp2', 'd2-inp2']
        assert outputs['complex_cap_indexed_by_id'] == {
            'dep1': 'd1-inp2',
            'dep2': 'd2-inp2',
        }

    def test_nonexistent_group(self):
        bp = models.Blueprint(id='bp', creator=self.user, tenant=self.tenant)
        dep4 = models.Deployment(
            id='dep4',
            outputs={
                'cap1': {'value': {
                    'get_group_capability': ['some-group-id', 'cap1'],
                }},
            },
            blueprint=bp, creator=self.user, tenant=self.tenant,
        )
        with self.assertRaisesRegex(
                CloudifyClientError, 'some-group-id') as cm:
            # get-group-cap of a group that doesnt exist is a 404
            self.client.deployments.outputs.get(dep4.id)
        assert cm.exception.status_code == 404


class TestGetEnvironmentCapability(base_test.BaseServerTestCase):

    def test_get_environment_capability(self):
        bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )
        env = models.Deployment(
            id='shared',
            blueprint=bp,
            capabilities={
                'node1_key': {
                    'value': {
                        'get_attribute': ['node1', 'key', 0, 'nested', 0]
                    },
                },
                'complex_capability': {
                    'value': {'level1': {'level2': {'level3': ['value1']}}}
                }
            },
            creator=self.user,
            tenant=self.tenant,
        )
        node1 = models.Node(
            id='node1',
            type='node',
            properties={'key': [{'nested': ['test_value']}]},
            deployment=env,
            creator=self.user,
            tenant=self.tenant,
            **node_intance_counts(1),
        )
        models.NodeInstance(
            id='node1_1',
            node=node1,
            state='started',
            creator=self.user,
            tenant=self.tenant,
        )
        child = models.Deployment(
            id='child',
            blueprint=bp,
            labels=[models.DeploymentLabel(
                key='csys-obj-parent',
                value=env.id,
                creator=self.user,
            )],
            outputs={
                'node1_key': {
                    'value': {'get_environment_capability': 'node1_key'},
                },
                'flattened': {
                    'value': {
                        'get_environment_capability': [
                            'complex_capability', 'level1', 'level2',
                            'level3', 0
                        ],
                    },
                }
            },
            creator=self.user,
            tenant=self.tenant,
        )

        outputs = self.client.deployments.outputs.get(child.id)['outputs']
        assert outputs['node1_key'] == 'test_value'
        assert outputs['flattened'] == 'value1'

# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

import pytest

from . import DeploymentUpdateBase, BLUEPRINT_ID

from integration_tests.tests.utils import wait_for_blueprint_upload

pytestmark = pytest.mark.group_deployments


class TestDeploymentUpdateMixedOperations(DeploymentUpdateBase):

    def test_add_node_and_relationship(self):
        """
        Base: site2 is connected_to site1
            site2=====>site1

        Modification:
         1. site3 added
         2. site3 connected_to site1.
         3. site2 connected_to site3.
         site2=====>site1
            \\         ^
             \\       //
              ->site3
        :return:
        """
        deployment, modified_bp_path = self._deploy_and_get_modified_bp_path(
                'add_node_and_relationship')

        node_mapping = {
            'stagnant': 'site1',
            'added_relationship': 'site2',
            'new': 'site3'
        }

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # check all operation have been executed
        self._assertDictContainsSubset(
                {'source_ops_counter': '3'},
                base_node_instances['added_relationship'][0]
                ['runtime_properties']
        )

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        # Get all related and affected nodes and node instances
        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['stagnant', 'added_relationship', 'new'],
                excluded_items=['plugins', 'relationships']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['stagnant', 'added_relationship', 'new'],
                excluded_items=
                ['runtime_properties', 'relationships', 'system_properties']
        )

        # Check that there is only 1 from each
        self.assertEqual(1, len(modified_nodes['stagnant']))
        self.assertEqual(1, len(modified_node_instances['stagnant']))
        self.assertEqual(1, len(modified_nodes['added_relationship']))
        self.assertEqual(1,
                         len(modified_node_instances['added_relationship']))
        self.assertEqual(1, len(modified_nodes['new']))
        self.assertEqual(1, len(modified_node_instances['new']))

        # get the nodes and node instances
        added_relationship_node_instance = \
            modified_node_instances['added_relationship'][0]
        new_node = modified_nodes['new'][0]
        new_node_instance = modified_node_instances['new'][0]

        # assert there are 2 relationships total
        self.assertEqual(1, len(new_node.relationships))
        self.assertEqual(2,
                         len(added_relationship_node_instance.relationships))

        # check the relationship between site2 and site1 is intact
        self._assert_relationship(
                added_relationship_node_instance.relationships,
                target='site1',
                expected_type='cloudify.relationships.connected_to')

        # check new relationship between site2 and site3
        self._assert_relationship(
                added_relationship_node_instance.relationships,
                target='site3',
                expected_type='cloudify.relationships.connected_to')

        # check the new relationship between site3 and site1 is in place
        self._assert_relationship(
                new_node.relationships,
                target='site1',
                expected_type='cloudify.relationships.connected_to')

        # check all operation have been executed.
        # source_ops_counter was increased for each operation between site2 and
        # site1, and another source_ops_counter increasing operation was the
        # establish between site2 and site3
        self._assertDictContainsSubset(
                {'source_ops_counter': '4'},
                added_relationship_node_instance['runtime_properties']
        )

        self._assertDictContainsSubset(
                {'source_ops_counter': '3'},
                new_node_instance['runtime_properties']
        )

    def test_add_remove_and_modify_relationship(self):
        """
        site0 relationships:
        i   |    base   |   modification    |   comment
        -------------------------------------------------
        0.  |   site1   |       site6       |   new site   (and removed site1)
        1.  |   site2   |       site4       |   moved site (and removed site2)
        2.  |   site3   |       site2B      |   new site
        3.  |   site4   |       site3       |   moved site
        4.  |   site5   |         -         |   remove site5

        :return:
        """
        deployment, modified_bp_path = self._deploy_and_get_modified_bp_path(
                'add_remove_and_modify_relationship')
        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        node_mapping = {'source': 'site0'}
        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)
        modified_node = modified_nodes['source'][0]
        modified_node_instance = modified_node_instances['source'][0]

        # Assert relationship order
        rel_targets = ['site6', 'site4', 'site2B', 'site3']
        for index, rel_target in enumerate(rel_targets):
            self.assertEqual(
                    modified_node['relationships'][index]['target_id'],
                    rel_targets[index])

        for index, rel_target in enumerate(rel_targets):
            self.assertEqual(
                    modified_node_instance[
                        'relationships'][index]['target_name'],
                    rel_targets[index]
            )

        # Assert all operation were executed
        # Pre update:
        # 1. establish site0->site3: source_ops_counter=1
        # 2. establish site0->site4: source_ops_counter=2
        # 3. establish site0->site5: source_ops_counter=3
        # Post update:
        # 5. unlink site0->site1: source_ops_counter=4
        # 6. unlink site0->site2: source_ops_counter=5
        # 7. establish site0->site6: source_ops_counter=6
        # 8. establish site0->site2B: source_ops_counter=7
        self._assertDictContainsSubset(
                {'source_ops_counter': '7'},
                modified_node_instance['runtime_properties']
        )

    def test_add_relationships_between_added_nodes(self):
        """
        Tests a creation of a deployment from scratch.

        The original deployment contains only one node that will be removed.
        The following diagrams depicts the new deployment:
                            e
                           / \
                          c  d
                         / \
                        a   b       f
        All of the relationships are of contained in type and the direction
        is upward. i.e. a contained in c and d contained in e. f is the only
        node which has no relationships from it or to it.
        :return:
        """
        deployment, modified_bp_path = self._deploy_and_get_modified_bp_path(
                'add_relationships_between_added_nodes')

        node_mapping = {
            'a': 'site_a',
            'b': 'site_b',
            'c': 'site_c',
            'd': 'site_d',
            'e': 'site_e',
            'f': 'site_f'
        }
        node_ids = set(node_mapping.keys())
        root_node_ids = {'e', 'f'}

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        nodes, node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        node_instances = {k: v[0] for k, v in node_instances.items()}

        # Assert that f isn't connected to any node, and all of the install
        # operation ran
        for node in root_node_ids:
            self.assertEqual(0, len(node_instances[node]['relationships']))

        # Assert that each node instance had only 1 relationship
        for node in node_ids - root_node_ids:
            self.assertEqual(1, len(node_instances[node]['relationships']))

        # Assert that node a, b, c and d have started correctly
        for node in node_ids - root_node_ids:
            self._assertDictContainsSubset(
                    {'{0}_ops_counter'.format(node): str(3)},
                    node_instances[node]['runtime_properties'])

        # Assert that b and d established relationships successfully
        # through source runtime properties
        for node in {'b', 'd'}:
            self._assertDictContainsSubset(
                    {'source_ops_counter_{0}'.format(node):  str(1)},
                    node_instances[node]['runtime_properties'])

        # Assert that a and c  established relationships successfully
        # through target runtime properties of node e and c (respectively)
        for node in {'e', 'c'}:
            self._assertDictContainsSubset(
                    {'target_ops_counter': str(1)},
                    node_instances[node]['runtime_properties'])

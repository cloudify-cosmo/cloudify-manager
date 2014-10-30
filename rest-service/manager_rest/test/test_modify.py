#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'idanmo'

import uuid

from base_test import BaseServerTestCase


class ModifyTests(BaseServerTestCase):

    def test_modify_add_instance(self):
        _, _, _, deployment = self.put_deployment(
            deployment_id=str(uuid.uuid4()),
            blueprint_file_name='modify1.yaml')

        node_instances1 = self.client.node_instances.list()
        self.assertEqual(2, len(node_instances1))
        self._assert_number_of_instances(deployment.id, 'node1', 1, 1)

        modified_nodes = {'node1': {'instances': 2}}
        modification = self.client.deployments.modify.start(
            deployment.id, nodes=modified_nodes)

        self._assert_number_of_instances(deployment.id, 'node1', 1, 1)

        self.assertEqual(modified_nodes, modification.modified_nodes)
        node_instances2 = self.client.node_instances.list()
        self.assertEqual(3, len(node_instances2))

        initial_instance_ids = [i2.id for i2 in node_instances1]
        new_instances = [i for i in node_instances2
                         if i.id not in initial_instance_ids]
        old_instances = [i for i in node_instances2
                         if i.id in initial_instance_ids]
        self.assertEqual(1, len(new_instances))
        self.assertEqual(2, len(old_instances))

        new_instance = new_instances[0]
        self.assertEqual('node1', new_instance.node_id)
        self.assertEqual(sorted(old_instances, key=lambda _i: _i.id),
                         sorted(node_instances1, key=lambda _i: _i.id))

        added_and_related = modification.node_instances.added_and_related
        self.assertEqual(2, len(added_and_related))

        self.client.deployments.modify.finish(deployment.id, modification)

        self._assert_number_of_instances(deployment.id, 'node1', 2, 1)

        node_instances3 = self.client.node_instances.list()
        self.assertEqual(3, len(node_instances3))

        node1_instance_ids = [i.id for i in node_instances3
                              if i.node_id == 'node1']
        node2_instance = [i for i in node_instances3
                          if i.node_id == 'node2'][0]
        node2_target_ids = [rel['target_id'] for rel
                            in node2_instance.relationships]
        self.assertEqual(set(node1_instance_ids), set(node2_target_ids))

    def test_modify_remove_instance(self):
        _, _, _, deployment = self.put_deployment(
            deployment_id=str(uuid.uuid4()),
            blueprint_file_name='modify2.yaml')

        node_instances1 = self.client.node_instances.list()
        self.assertEqual(3, len(node_instances1))
        self._assert_number_of_instances(deployment.id, 'node1', 2, 2)

        modified_nodes = {'node1': {'instances': 1}}
        modification = self.client.deployments.modify.start(
            deployment.id, nodes=modified_nodes)

        self._assert_number_of_instances(deployment.id, 'node1', 2, 2)

        self.assertEqual(modified_nodes, modification.modified_nodes)
        node_instances2 = self.client.node_instances.list()
        self.assertEqual(3, len(node_instances2))

        initial_instance_ids = [i2.id for i2 in node_instances1]
        new_instances = [i for i in node_instances2
                         if i.id not in initial_instance_ids]
        old_instances = [i for i in node_instances2
                         if i.id in initial_instance_ids]
        self.assertEqual(0, len(new_instances))
        self.assertEqual(3, len(old_instances))

        self.assertEqual(sorted(old_instances, key=lambda _i: _i.id),
                         sorted(node_instances1, key=lambda _i: _i.id))

        removed_and_related = modification.node_instances.removed_and_related
        self.assertEqual(2, len(removed_and_related))

        self.client.deployments.modify.finish(deployment.id, modification)

        self._assert_number_of_instances(deployment.id, 'node1', 1, 2)

        node_instances3 = self.client.node_instances.list()
        self.assertEqual(2, len(node_instances3))

        node1_instance_id = [i.id for i in node_instances3
                             if i.node_id == 'node1'][0]
        node2_instance = [i for i in node_instances3
                          if i.node_id == 'node2'][0]
        node2_target_ids = [rel['target_id'] for rel
                            in node2_instance.relationships]
        self.assertEqual(1, len(node2_target_ids))
        self.assertEqual(node1_instance_id, node2_target_ids[0])

    def _assert_number_of_instances(self,
                                    deployment_id, node_id,
                                    expected_number_of_instances,
                                    expected_deploy_number_of_instances):
        node = self.client.nodes.get(deployment_id, node_id)
        self.assertEqual(expected_deploy_number_of_instances,
                         node.deploy_number_of_instances)
        self.assertEqual(expected_number_of_instances,
                         node.number_of_instances)

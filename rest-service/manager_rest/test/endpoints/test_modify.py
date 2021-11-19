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

import copy
import uuid
import dateutil.parser
from datetime import timedelta

from manager_rest.test.base_test import CLIENT_API_VERSION

from manager_rest import utils
from manager_rest.test import base_test
from cloudify_rest_client import exceptions
from cloudify_rest_client.deployment_modifications import (
    DeploymentModification)


EXPECTS_SCALING_GROUPS = CLIENT_API_VERSION not in ['v1', 'v2']


class ModifyTests(base_test.BaseServerTestCase):

    def test_data_model_with_finish(self):
        def expected_after_end_func(_, before_end):
            return before_end
        self._test_data_model_impl(
            end_func=self.client.deployment_modifications.finish,
            expected_end_status=DeploymentModification.FINISHED,
            expected_end_node_counts={
                'num': 2, 'deploy_num': 1, 'planned_num': 2},
            expected_before_end_func=lambda before_end: [],
            expected_after_end_func=expected_after_end_func,
            expected_after_end_count=3,
            expected_after_end_runtime_property='after_start')

    def test_data_model_with_rollback(self):
        def expected_after_end_func(before_modification, _):
            return before_modification
        self._test_data_model_impl(
            end_func=self.client.deployment_modifications.rollback,
            expected_end_status=DeploymentModification.ROLLEDBACK,
            expected_end_node_counts={
                'num': 1, 'deploy_num': 1, 'planned_num': 1},
            expected_before_end_func=lambda before_end: before_end,
            expected_after_end_func=expected_after_end_func,
            expected_after_end_count=2,
            expected_after_end_runtime_property='before_start')

    def _test_data_model_impl(
            self,
            end_func,
            expected_end_status,
            expected_end_node_counts,
            expected_before_end_func,
            expected_after_end_func,
            expected_after_end_count,
            expected_after_end_runtime_property):

        def node_assertions(num, deploy_num, planned_num):
            node = self.client.nodes.get(deployment.id, 'node1')
            self.assertEqual(node.number_of_instances, num)
            self.assertEqual(node.planned_number_of_instances, planned_num)
            self.assertEqual(node.deploy_number_of_instances, deploy_num)

        _, _, _, deployment = self.put_deployment(
            deployment_id='d{0}'.format(uuid.uuid4()),
            blueprint_file_name='modify1.yaml')

        node_assertions(num=1, deploy_num=1, planned_num=1)

        mock_context = {'some': 'data'}

        node1_instance = self.client.node_instances.list(
            deployment_id=deployment.id, node_name='node1')[0]
        self.client.node_instances.update(
            node1_instance.id,
            runtime_properties={'test': 'before_start'},
            version=1)
        node2_instance = self.client.node_instances.list(
            deployment_id=deployment.id, node_name='node2')[0]
        self.client.node_instances.update(
            node2_instance.id,
            runtime_properties={'test': 'before_start'},
            version=1)

        before_modification = self._get_items(
            self.client.node_instances.list,
            deployment_id=deployment.id
        )
        modified_nodes = {'node1': {'instances': 2}}
        modification = self.client.deployment_modifications.start(
            deployment.id, nodes=modified_nodes, context=mock_context)
        self._fix_modification(modification)

        self._assert_instances_equal(
            modification.node_instances.before_modification,
            before_modification)
        self.assertIsNone(modification.ended_at)

        self.client.node_instances.update(
            node1_instance.id,
            runtime_properties={'test': 'after_start'},
            version=2)
        self.client.node_instances.update(
            node2_instance.id,
            runtime_properties={'test': 'after_start'},
            # version is 3 here because the modification increased it by 1
            version=3)

        node_assertions(num=1, deploy_num=1, planned_num=2)

        modification_id = modification.id
        self.assertEqual(modification.status,
                         DeploymentModification.STARTED)

        before_end = self._get_items(self.client.node_instances.list,
                                     deployment_id=deployment.id)

        node1_instances = self.client.node_instances.list(
            deployment_id=deployment.id, node_name='node1')
        node2_instance1 = self.client.node_instances.list(
            deployment_id=deployment.id, node_name='node2')[0]
        self.assertEqual(
            node1_instances[0]['index'],
            node1_instance['index'])
        self.assertEqual(
            node2_instance1['index'],
            node2_instance['index'])
        self.assertNotEqual(
            node1_instances[0]['index'],
            node1_instances[1]['index'])

        end_func(modification_id)
        after_end = self._get_items(self.client.node_instances.list,
                                    deployment_id=deployment.id)

        node_assertions(**expected_end_node_counts)

        modification = self.client.deployment_modifications.get(
            modification.id)
        self._fix_modification(modification)
        self.assertEqual(modification.id, modification_id)
        self.assertEqual(modification.status, expected_end_status)
        self.assertEqual(modification.deployment_id, deployment.id)
        self.assertEqual(modification.modified_nodes, modified_nodes)
        created_at = dateutil.parser.parse(modification.created_at)
        ended_at = dateutil.parser.parse(modification.ended_at)
        self.assertTrue(
            dateutil.parser.parse(utils.get_formatted_timestamp()) -
            timedelta(seconds=5) <=
            created_at <= ended_at <=
            dateutil.parser.parse(utils.get_formatted_timestamp()))
        all_modifications = self._get_items(
            self.client.deployment_modifications.list
        )
        dep_modifications = self._get_items(
            self.client.deployment_modifications.list,
            deployment_id=deployment.id
        )
        for modification in all_modifications + dep_modifications:
            self._fix_modification(modification)
        self.assertEqual(len(dep_modifications), 1)
        self.assertEqual(dep_modifications[0], modification)
        self.assertEqual(all_modifications, dep_modifications)
        modifications_list = self._get_items(
            self.client.deployment_modifications.list,
            deployment_id='i_really_should_not_exist'
        )
        self.assertEqual([], modifications_list)
        self._assert_instances_equal(
            modification.node_instances.before_modification,
            before_modification)
        self._assert_instances_equal(
            modification.node_instances.before_rollback,
            expected_before_end_func(before_end))

        self._assert_instances_equal(
            after_end,
            expected_after_end_func(before_modification, before_end))

        self.assertEqual(modification.context, mock_context)

        self.assertEqual(expected_after_end_count, len(after_end))

        self.assertEqual(
            self.client.node_instances.get(
                node1_instance.id).runtime_properties['test'],
            expected_after_end_runtime_property)
        self.assertEqual(
            self.client.node_instances.get(
                node2_instance.id).runtime_properties['test'],
            expected_after_end_runtime_property)

    def _assert_instances_equal(self, instances1, instances2):
        def sort_key(instance):
            return instance['id']
        self.assertEqual(sorted(instances1, key=sort_key),
                         sorted(instances2, key=sort_key))

    @staticmethod
    def _fix_modification(modification):
        if not EXPECTS_SCALING_GROUPS:
            for node_instances in modification.node_instances.values():
                for node_instance in node_instances:
                    node_instance.pop('scaling_groups', None)

    def _get_items(self, list_func, *args, **kwargs):
        if CLIENT_API_VERSION != 'v1':
            items = list_func(*args, **kwargs).items
        else:
            items = list_func(*args, **kwargs)
        return items

    def test_no_concurrent_modifications(self):
        blueprint_id, _, _, deployment = self.put_deployment(
            deployment_id='d{0}'.format(uuid.uuid4()),
            blueprint_file_name='modify1.yaml')
        deployment2 = self.client.deployments.create(
            blueprint_id=blueprint_id,
            deployment_id='d{0}'.format(uuid.uuid4()))
        self.create_deployment_environment(deployment=deployment2)
        modification = self.client.deployment_modifications.start(
            deployment.id, nodes={})
        # should not allow another deployment modification of the same
        # deployment to start
        with self.assertRaises(
                exceptions.ExistingStartedDeploymentModificationError) as e:
            self.client.deployment_modifications.start(deployment.id, nodes={})
        self.assertIn(modification.id, str(e.exception))

        # should allow another deployment modification of a different
        # deployment to start
        self.client.deployment_modifications.start(deployment2.id, nodes={})

        self.client.deployment_modifications.finish(modification.id)
        # should allow deployment modification to start after previous one
        # finished
        self.client.deployment_modifications.start(deployment.id, nodes={})

    def test_finish_and_rollback_on_ended_modification(self):
        def test(end_function):
            _, _, _, deployment = self.put_deployment(
                deployment_id='d{0}'.format(uuid.uuid4()),
                blueprint_id='b{0}'.format(uuid.uuid4()),
                blueprint_file_name='modify1.yaml')
            modification = self.client.deployment_modifications.start(
                deployment.id, nodes={})
            end_function(modification.id)

            with self.assertRaises(
                    exceptions.DeploymentModificationAlreadyEndedError):
                self.client.deployment_modifications.finish(modification.id)
            with self.assertRaises(
                    exceptions.DeploymentModificationAlreadyEndedError):
                self.client.deployment_modifications.rollback(modification.id)

        test(self.client.deployment_modifications.finish)
        test(self.client.deployment_modifications.rollback)

    def test_finish_and_rollback_on_non_existent_modification(self):
        with self.assertRaises(exceptions.CloudifyClientError) as scope:
            self.client.deployment_modifications.finish('what')
        self.assertEqual(scope.exception.status_code, 404)
        self.assertEqual(str(scope.exception),
                         '404: Requested `DeploymentModification` '
                         'with ID `what` was not found')

        with self.assertRaises(exceptions.CloudifyClientError) as scope:
            self.client.deployment_modifications.rollback('what')
        self.assertEqual(scope.exception.status_code, 404)
        self.assertEqual(str(scope.exception),
                         '404: Requested `DeploymentModification` '
                         'with ID `what` was not found')

    def test_modify_add_instance(self):
        _, _, _, deployment = self.put_deployment(
            deployment_id='d{0}'.format(uuid.uuid4()),
            blueprint_file_name='modify1.yaml')

        node_instances1 = self.client.node_instances.list()
        self.assertEqual(2, len(node_instances1))
        self._assert_number_of_instances(deployment.id, 'node1', 1, 1)

        modified_nodes = {'node1': {'instances': 2}}
        modification = self.client.deployment_modifications.start(
            deployment.id, nodes=modified_nodes)

        self._assert_number_of_instances(deployment.id, 'node1', 1, 1)

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
        expected_old_instances = copy.deepcopy(node_instances1)
        for instance in expected_old_instances:
            if instance.node_id == 'node2':
                current_relationship = instance.relationships[0]
                new_relationship = copy.deepcopy(current_relationship)
                new_relationship['target_id'] = new_instance.id
                instance.relationships.append(new_relationship)
                instance['version'] += 1
        self.assertEqual(sorted(old_instances, key=lambda _i: _i.id),
                         sorted(expected_old_instances, key=lambda _i: _i.id))

        added_and_related = modification.node_instances.added_and_related
        self.assertEqual(2, len(added_and_related))

        self.client.deployment_modifications.finish(modification.id)

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
            deployment_id='d{0}'.format(uuid.uuid4()),
            blueprint_file_name='modify2.yaml')

        node_instances1 = self.client.node_instances.list()
        self.assertEqual(3, len(node_instances1))
        self._assert_number_of_instances(deployment.id, 'node1', 2, 2)

        modified_nodes = {'node1': {'instances': 1}}
        modification = self.client.deployment_modifications.start(
            deployment.id, nodes=modified_nodes)

        self._assert_number_of_instances(deployment.id, 'node1', 2, 2)

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

        self.client.deployment_modifications.finish(modification.id)

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

    def test_scaling_groups_finish(self):
        self._test_scaling_groups(
            end_method=self.client.deployment_modifications.finish,
            end_expectation={'current': 2, 'planned': 2})

    def test_scaling_groups_rollback(self):
        self._test_scaling_groups(
            end_method=self.client.deployment_modifications.rollback,
            end_expectation={'current': 1, 'planned': 1})

    def _test_scaling_groups(self, end_method, end_expectation):
        _, _, _, deployment = self.put_deployment(
            blueprint_file_name='modify3-scale-groups.yaml')

        def assert_deployment_instances(dep, current, planned):
            props = dep['scaling_groups']['group']['properties']
            self.assertEqual(current, props['current_instances'])
            self.assertEqual(planned, props['planned_instances'])

        def assert_instances(current, planned):
            # Test get and list deployments endpoints
            dep1 = self.client.deployments.get(deployment.id)
            dep2 = self.client.deployments.list()[0]
            for dep in [dep1, dep2]:
                assert_deployment_instances(dep, current, planned)

        assert_deployment_instances(deployment, current=1, planned=1)
        assert_instances(current=1, planned=1)

        modified_nodes = {'group': {'instances': 2}}
        modification = self.client.deployment_modifications.start(
            deployment.id, nodes=modified_nodes)

        assert_instances(current=1, planned=2)

        # verify node instances scaling groups are also updated for newly
        # added nodes
        node_instances = self.client.node_instances.list(
            deployment_id=deployment.id
        ).items
        self.assertEqual(2, len(node_instances))
        self.assertIsNotNone(node_instances[0]['index'])
        self.assertIsNotNone(node_instances[1]['index'])
        self.assertNotEqual(node_instances[0]['index'],
                            node_instances[1]['index'])

        for instance in node_instances:
            node_instance_scaling_groups = instance['scaling_groups']
            self.assertEqual(1, len(node_instance_scaling_groups))
            self.assertEqual('group', node_instance_scaling_groups[0]['name'])

        end_method(modification.id)

        assert_instances(**end_expectation)

        deployment = self.client.deployments.get(deployment.id)
        self.client.deployments.delete(deployment.id)
        assert_deployment_instances(deployment, **end_expectation)

    def test_relationship_order_of_related_nodes(self):
        _, _, _, deployment = self.put_deployment(
            blueprint_file_name='modify4-relationship-order.yaml')
        modification = self.client.deployment_modifications.start(
            deployment_id=deployment.id,
            nodes={'node{}'.format(index): {'instances': 2}
                   for index in [1, 2, 4, 5]})
        self.client.deployment_modifications.finish(modification.id)

        node6 = self.client.node_instances.list(node_id='node6')[0]
        expected = [
            ('node1', 'connected_to'),
            ('node1', 'connected_to'),
            ('node2', 'connected_to'),
            ('node2', 'connected_to'),
            ('node3', 'contained_in'),
            ('node4', 'connected_to'),
            ('node4', 'connected_to'),
            ('node5', 'connected_to'),
            ('node5', 'connected_to'),
        ]
        relationships = node6.relationships
        self.assertEqual(len(expected), len(relationships))
        for (target_name, tpe), relationship in zip(expected, relationships):
            self.assertDictContainsSubset({
                'target_name': target_name,
                'type': 'cloudify.relationships.{0}'.format(tpe)
            }, relationship)

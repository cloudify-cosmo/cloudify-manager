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
import os
import shutil
import time
import tempfile

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import tar_blueprint

from dsl_parser.interfaces.utils import no_op_operation
from cloudify_rest_client.exceptions import CloudifyClientError
from manager_rest.deployment_update.constants import STATES
from manager_rest.models import Execution

blueprints_base_path = 'dsl/deployment_update'


class DeploymentUpdateBase(TestCase):

    def _wait_for(self,
                  callable_obj,
                  callable_obj_key,
                  value_attr,
                  test_value,
                  test_condition,
                  msg='',
                  timeout=900):
        deadline = time.time() + timeout
        while True:
            if time.time() > deadline:
                raise Exception(msg)
            value = callable_obj(callable_obj_key)
            if test_condition(getattr(value, value_attr), test_value):
                return value
            time.sleep(3)

    def _wait_for_committed_state(self, depup_id):
        error_msg = 'deployment update {0} failed to commit'.format(depup_id)
        return self._wait_for(self.client.deployment_updates.get,
                              depup_id,
                              'state',
                              STATES.COMMITTED,
                              lambda x, y: x == y,
                              error_msg)

    def _wait_for_execution(self, execution):
        # Poll for execution status until execution ends
        error_msg = 'execution of operation {0} for deployment {1} timed out'\
            .format(execution.workflow_id, execution.deployment_id)
        return self._wait_for(self.client.executions.get,
                              execution.id,
                              'status',
                              Execution.END_STATES,
                              lambda x, y: x in y,
                              error_msg)

    def _assert_relationship(self, relationships, target,
                             expected_type=None, exists=True):
        """
        assert that a node/node instance has a specific relationship
        :param relationships: node/node instance relationships list
        :param target: target name (node id, not instance id)
        :param expected_type: expected relationship type
        """
        expected_type = expected_type or 'cloudify.relationships.contained_in'
        error_msg = 'relationship of target "{0}" ' \
                    'and type "{1}" is missing'.format(target, expected_type)

        for relationship in relationships:
            relationship_type = relationship['type']
            relationship_target = (relationship.get('target_name') or
                                   relationship.get('target_id'))

            if (relationship_type == expected_type and
                    relationship_target == target):
                if not exists:
                    self.fail(error_msg)
                return

        if exists:
            self.fail(error_msg.format(target, expected_type))

    def _deploy_and_get_modified_bp_path(self, test_name, inputs=None):

        base_dir = os.path.join(test_name, 'base')
        modified_dir = os.path.join(test_name, 'modification')
        base_bp = '{0}_base.yaml'.format(test_name)
        modified_bp = '{0}_modification.yaml'.format(test_name)

        base_bp_path = \
            resource(os.path.join(blueprints_base_path,
                                  base_dir,
                                  base_bp))
        deployment, _ = deploy(base_bp_path, inputs=inputs)

        modified_bp_path = \
            resource(os.path.join(blueprints_base_path,
                                  modified_dir,
                                  modified_bp))
        return deployment, modified_bp_path

    def _wait_for_execution_to_terminate(self, deployment_id, workflow_id):
        # wait for 'update' workflow to finish
        executions = \
            self.client.executions.list(deployment_id=deployment_id,
                                        workflow_id=workflow_id)
        for execution in executions:
            execution_status = self._wait_for_execution(execution)
            self.assertEquals('terminated', execution_status['status'],
                              execution_status.error)

    def _get_nodes_and_node_instances_dict(self, deployment_id, dct):
        nodes_dct = {k: [] for k, _ in dct.iteritems()}
        node_instances_dct = {k: [] for k, _ in dct.iteritems()}

        for k, v in dct.iteritems():
            nodes = [n for n in self.client.nodes.list(deployment_id,
                                                       node_id=dct[k])]
            node_instances = \
                [n for n in self.client.node_instances.list(deployment_id,
                                                            node_id=dct[k])]
            nodes_dct[k].extend(nodes)
            node_instances_dct[k].extend(node_instances)

        return nodes_dct, node_instances_dct

    def _assert_equal_entity_dicts(self,
                                   old_nodes,
                                   new_nodes,
                                   keys,
                                   excluded_items=()):

        old_nodes_by_id = \
            {n['id']: n for k in keys for n in old_nodes.get(k, {})}
        new_nodes_by_id = \
            {n['id']: n for k in keys for n in new_nodes.get(k, {})}

        intersecting_ids = \
            set(old_nodes_by_id.keys()) & set(new_nodes_by_id.keys())
        for id in intersecting_ids:
            self._assert_equal_dicts(old_nodes_by_id[id],
                                     new_nodes_by_id[id],
                                     excluded_items=excluded_items)

    def _assert_equal_dicts(self, d1, d2, excluded_items=()):
        for k, v in d1.iteritems():
            if k not in excluded_items:
                self.assertEquals(d2.get(k, None), v,
                                  '{0} has changed on {1}. {2}!={3}'
                                  .format(d1, k, d1[k], d2[k]))

    def _create_dict(self, path):
        if len(path) == 1:
            return path[0]
        else:
            return {path[0]: self._create_dict(path[1:])}


class TestDeploymentUpdateAddition(DeploymentUpdateBase):

    def test_add_node_bp(self):
        self._test_add_node(archive_mode=False)

    def test_add_node_archive(self):
        self._test_add_node(archive_mode=True)

    def _test_add_node(self, archive_mode=False):
        """
        add a node (type exists) which is contained in an existing node
        - assert that both node and node instance have been created
        - assert the node/instance relationships have been created
        - assert the 'update' workflow has been executed and
          all related operations were executed as well
        """

        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_node')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'intact': 'site1',
                     'added': 'site2'})

        tempdir = tempfile.mkdtemp()
        try:
            if archive_mode:
                tar_path = tar_blueprint(modified_bp_path, tempdir)
                dep_update = self.client.deployment_updates. \
                    stage_archive(deployment.id, tar_path,
                                  os.path.basename(modified_bp_path))
            else:
                dep_update = \
                    self.client.deployment_updates.stage(deployment.id,
                                                         modified_bp_path)

            self.client.deployment_updates.add(
                    dep_update.id,
                    entity_type='node',
                    entity_id='nodes:site2')
            self.client.deployment_updates.commit(dep_update.id)

            # wait for 'update' workflow to finish
            self._wait_for_execution_to_terminate(deployment.id, 'update')
            self._wait_for_committed_state(dep_update.id)

            modified_nodes, modified_node_instances = \
                self._get_nodes_and_node_instances_dict(deployment.id,
                                                        {'intact': 'site1',
                                                         'added': 'site2'})

            # assert all unaffected nodes and node instances remained intact
            self._assert_equal_entity_dicts(
                    base_nodes,
                    modified_nodes,
                    keys=['intact', 'added'],
                    excluded_items=['runtime_properties', 'plugins']
            )

            self._assert_equal_entity_dicts(
                    base_node_instances,
                    modified_node_instances,
                    keys=['intact', 'added'],
                    excluded_items=['runtime_properties']
            )

            # assert that node and node instance were added to storage
            self.assertEquals(1, len(modified_nodes['added']))
            self.assertEquals(1, len(modified_node_instances['added']))

            # assert that node has a relationship
            node = modified_nodes['added'][0]
            self.assertEquals(1, len(node.relationships))
            self._assert_relationship(
                    node.relationships,
                    target='site1',
                    expected_type='cloudify.relationships.contained_in')
            self.assertEquals(node.type, 'cloudify.nodes.WebServer')

            # assert that node instance has a relationship
            added_instance = modified_node_instances['added'][0]
            self.assertEquals(1, len(added_instance.relationships))
            self._assert_relationship(
                    added_instance.relationships,
                    target='site1',
                    expected_type='cloudify.relationships.contained_in')

            # assert all operations in 'update' ('install') workflow
            # are executed by making them increment a runtime property
            self.assertDictContainsSubset({'source_ops_counter': '6'},
                                          added_instance['runtime_properties'])

            # assert operations affected the target node as well
            add_related_instance = \
                self.client.node_instances.list(deployment_id=deployment.id,
                                                node_id='site1')[0]
            self.assertDictContainsSubset(
                    {'target_ops_counter': '3'},
                    add_related_instance['runtime_properties']
            )
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)

    def test_add_node_operation(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_node_operation')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id, {'modified': 'site1'})

        dep_update = self.client.deployment_updates.stage(deployment.id,
                                                          modified_bp_path)

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='operation',
                entity_id='nodes:site1:operations:'
                          'cloudify.interfaces.lifecycle.create')

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        # assert nothing changed except for plugins and operations
        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id, {'modified': 'site1'})

        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['modified'],
                excluded_items=['plugins', 'operations']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['modified']
        )

        # Execute the newly modified operation
        self.client.executions.start(
                deployment.id,
                'execute_operation',
                parameters={
                    'operation': 'cloudify.interfaces.lifecycle.create'
                }
        )
        self._wait_for_execution_to_terminate(deployment.id,
                                              'execute_operation')

        # Check again for the nodes and node instances and check
        # their runtime properties
        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id, {'modified': 'site1'})

        self.assertEqual(len(modified_nodes['modified']), 1)
        added_node = modified_nodes['modified'][0]
        self.assertEqual(len(modified_node_instances['modified']), 1)
        added_node_instance = modified_node_instances['modified'][0]

        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['modified'],
                excluded_items=['plugins', 'operations']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['modified'],
                excluded_items=['runtime_properties']
        )

        affected_lifecycle_operation = added_node['operations'].get(
                'cloudify.interfaces.lifecycle.create')
        self.assertIsNotNone(affected_lifecycle_operation)

        self.assertDictContainsSubset(
                {'source_ops_counter': '1'},
                added_node_instance['runtime_properties']
        )

    def test_add_node_with_multiple_instances(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_node_'
                                                  'with_multiple_instances')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'intact': 'site1',
                     'added': 'site2'})

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='node',
                entity_id='nodes:site2')
        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(deployment.id,
                                                    {'intact': 'site1',
                                                     'added': 'site2'})

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['intact'],
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['intact'],
                excluded_items=['runtime_properties']
        )

        # assert that node and node instance were added to storage
        self.assertEquals(1, len(modified_nodes['added']))
        self.assertEquals(3, len(modified_node_instances['added']))

        # assert that node has a relationship
        for node in modified_nodes['added']:
            self.assertEquals(1, len(node.relationships))
            self._assert_relationship(
                    node.relationships,
                    target='site1',
                    expected_type='cloudify.relationships.contained_in')
            self.assertEquals(node.type, 'cloudify.nodes.WebServer')

        # assert that node instance has a relationship
        for added_instance in modified_node_instances['added']:
            self.assertEquals(1, len(added_instance.relationships))
            self._assert_relationship(
                    added_instance.relationships,
                    target='site1',
                    expected_type='cloudify.relationships.contained_in')

            # assert all operations in 'update' ('install') workflow
            # are executed by making them increment a runtime property
            self.assertDictContainsSubset({'source_ops_counter': '6'},
                                          added_instance['runtime_properties'])

    def test_add_relationship(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_relationship')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'related': 'site1',
                     'target': 'site2',
                     'source': 'site3'})

        # check that the relationship operation between site3 and site 1
        # ran only once (at bp)
        self.assertDictContainsSubset(
                {'target_ops_counter': '1'},
                base_node_instances['related'][0]['runtime_properties']
        )

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='relationship',
                entity_id='nodes:site3:relationships:[1]')

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'related': 'site1',
                     'target': 'site2',
                     'source': 'site3'})

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['related', 'target', 'source'],
                excluded_items=['runtime_properties',
                                'plugins',
                                'relationships']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['related', 'target', 'source'],
                excluded_items=['runtime_properties', 'relationships']
        )

        # Check that there is only 1 from each
        self.assertEquals(1, len(modified_nodes['related']))
        self.assertEquals(1, len(modified_node_instances['related']))
        self.assertEquals(1, len(modified_nodes['target']))
        self.assertEquals(1, len(modified_node_instances['target']))
        self.assertEquals(1, len(modified_nodes['source']))
        self.assertEquals(1, len(modified_node_instances['source']))

        # get the nodes and node instances
        related_node_instance = modified_node_instances['related'][0]
        target_node_instance = modified_node_instances['target'][0]
        source_node = modified_nodes['source'][0]
        source_node_instance = modified_node_instances['source'][0]

        # assert there are 2 relationships total
        self.assertEquals(2, len(source_node.relationships))
        self.assertEquals(2, len(source_node_instance.relationships))

        # check the relationship between site2 and site0 is intact
        self._assert_relationship(
                source_node_instance.relationships,
                target='site1',
                expected_type='cloudify.relationships.connected_to')
        self._assert_relationship(
                source_node.relationships,
                target='site1',
                expected_type='cloudify.relationships.connected_to')

        # check the new relationship between site2 and site1 is in place
        self._assert_relationship(
                source_node_instance.relationships,
                target='site2',
                expected_type='new_relationship_type')
        self._assert_relationship(
                source_node.relationships,
                target='site2',
                expected_type='new_relationship_type')

        # check that the relationship operation between site3 and site 1
        # ran only once (at bp)
        self.assertDictContainsSubset(
                {'target_ops_counter': '1'},
                related_node_instance['runtime_properties']
        )

        # check all operation have been executed
        self.assertDictContainsSubset(
                {'source_ops_counter': '1'},
                source_node_instance['runtime_properties']
        )

        self.assertDictContainsSubset(
                {'target_ops_counter': '1'},
                target_node_instance['runtime_properties']
        )

    def test_add_relationship_operation(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_relationship_operation')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'target': 'site1',
                     'source': 'site2'})

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='operation',
                entity_id='nodes:site2:relationships:[0]:source_operations:'
                          'cloudify.interfaces.relationship_lifecycle.'
                          'establish'
        )
        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='operation',
                entity_id='nodes:site2:relationships:[0]:source_operations:'
                          'establish'
        )

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'target': 'site1',
                     'source': 'site2'})

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['target', 'source'],
                excluded_items=['relationships']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['target', 'source'],
                excluded_items=['relationships']
        )

        # Check that there is only 1 from each
        self.assertEquals(1, len(modified_nodes['target']))
        self.assertEquals(1, len(modified_node_instances['target']))
        self.assertEquals(1, len(modified_nodes['source']))
        self.assertEquals(1, len(modified_node_instances['source']))

        # get the nodes and node instances
        source_node = modified_nodes['source'][0]
        source_node_instance = modified_node_instances['source'][0]

        # assert there are 0 relationships
        self.assertEquals(1, len(source_node.relationships))
        self.assertEquals(1, len(source_node_instance.relationships))

        # check the new relationship between site2 and site1 is in place
        self._assert_relationship(
                source_node_instance.relationships,
                target='site1',
                expected_type='new_relationship_type')
        self._assert_relationship(
                source_node.relationships,
                target='site1',
                expected_type='new_relationship_type')

        dict_to_check = self._create_dict(['inputs', 'script_path',
                                           'increment.sh'])

        # check all operation have been executed
        source_operations = \
            source_node['relationships'][0]['source_operations']
        self.assertDictContainsSubset(
                dict_to_check,
                source_operations
                ['cloudify.interfaces.relationship_lifecycle.establish']
        )
        self.assertDictContainsSubset(
                dict_to_check,
                source_operations['establish']
        )

    def test_add_property(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_property')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'affected_node': 'site1'})
        base_node = base_nodes['affected_node'][0]

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='property',
                entity_id='nodes:site1:properties:ip')

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'affected_node': 'site1'})
        modified_node = modified_nodes['affected_node'][0]

        added_property = modified_node['properties'].get('ip')
        self.assertIsNotNone(added_property)
        self.assertEqual(added_property, '1.1.1.1')

        # assert nothing else changed
        self._assert_equal_dicts(base_node['properties'],
                                 modified_node['properties'],
                                 excluded_items=['ip'])

    def test_add_workflow(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_workflow')
        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='workflow',
                entity_id='workflows:my_custom_workflow')

        self.client.deployment_updates.commit(dep_update.id)

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id,
                                              'update')

        self.client.executions.start(dep_update.deployment_id,
                                     workflow_id='my_custom_workflow',
                                     parameters={
                                         'node_id': 'site1',
                                         'delta': 2
                                     })

        self._wait_for_execution_to_terminate(deployment.id,
                                              'my_custom_workflow')

        affected_node = \
            self.client.node_instances.list(dep_update.deployment_id,
                                            'site1')
        self.assertEqual(len(affected_node), 3)
        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertIn('my_custom_workflow',
                      [w['name'] for w in deployment.workflows])

    def test_add_output(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_output')
        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='output',
                entity_id='outputs:custom_output')

        self.client.deployment_updates.commit(dep_update.id)

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertDictContainsSubset({'custom_output': {'value': 0}},
                                      deployment.outputs)


class TestDeploymentUpdateRemoval(DeploymentUpdateBase):

    def test_remove_node(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('remove_node')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'remove_related': 'site1'})

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)
        self.client.deployment_updates.remove(
                dep_update.id,
                entity_type='node',
                entity_id='nodes:site2')

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(deployment.id,
                                                    {'remove_related': 'site1',
                                                     'removed': 'site2'})

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['remove_related', 'removed'],
                excluded_items=['runtime_properties']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['remove_related', 'removed'],
                excluded_items=['runtime_properties']
        )

        # assert that node and node instance were removed from storage
        self.assertEquals(0, len(modified_nodes['removed']))
        self.assertEquals(0, len(modified_node_instances['removed']))

        # assert relationship target remained intact
        self.assertEquals(1, len(modified_nodes['remove_related']))
        self.assertEquals(1, len(modified_node_instances['remove_related']))

        # assert all operations in 'update' ('install') workflow
        # are executed by making them increment a runtime property
        remove_related_instance = modified_node_instances['remove_related'][0]
        self.assertDictContainsSubset(
                {'target_ops_counter': '1'},
                remove_related_instance['runtime_properties']
        )

    def test_remove_node_operation(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path(
                    'remove_node_operation')

        # Execute the newly modified operation
        self.client.executions.start(
                deployment.id,
                'execute_operation',
                parameters={
                    'operation': 'cloudify.interfaces.lifecycle.stop'
                }
        )
        self._wait_for_execution_to_terminate(deployment.id,
                                              'execute_operation')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id, {'modified': 'site1'})

        self.assertDictContainsSubset(
                {'source_ops_counter': '1'},
                base_node_instances['modified'][0]['runtime_properties']
        )

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.remove(
                dep_update.id,
                entity_type='operation',
                entity_id='nodes:site1:operations:'
                          'cloudify.interfaces.lifecycle.stop')

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        # Execute the newly modified operation
        self.client.executions.start(
                deployment.id,
                'execute_operation',
                parameters={
                    'operation': 'cloudify.interfaces.lifecycle.stop'
                }
        )
        self._wait_for_execution_to_terminate(deployment.id,
                                              'execute_operation')

        # assert nothing changed except for plugins and operations
        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id, {'modified': 'site1'})

        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['modified'],
                excluded_items=['operations']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['modified']
        )

        modified_node = modified_nodes['modified'][0]

        affected_lifecycle_operation = \
            modified_node['operations']['cloudify.interfaces.lifecycle.stop']

        operation_template = \
            no_op_operation('cloudify.interfaces.lifecycle.stop')

        self.assertDictContainsSubset(operation_template,
                                      affected_lifecycle_operation)

    def test_remove_relationship(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('remove_relationship')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'related': 'site1',
                     'target': 'site2',
                     'source': 'site3'})

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.remove(
                dep_update.id,
                entity_type='relationship',
                entity_id='nodes:site3:relationships:[1]')

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        # Get all related and affected nodes and node instances
        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(deployment.id,
                                                    {'related': 'site1',
                                                     'target': 'site2',
                                                     'source': 'site3'})

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['related', 'target', 'source'],
                excluded_items=['runtime_properties', 'relationships']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['related', 'target', 'source'],
                excluded_items=['runtime_properties', 'relationships']
        )

        # Check that there is only 1 from each
        self.assertEquals(1, len(modified_nodes['related']))
        self.assertEquals(1, len(modified_node_instances['related']))
        self.assertEquals(1, len(modified_nodes['target']))
        self.assertEquals(1, len(modified_node_instances['target']))
        self.assertEquals(1, len(modified_nodes['source']))
        self.assertEquals(1, len(modified_node_instances['source']))

        # get the nodes and node instances
        target_node_instance = modified_node_instances['target'][0]
        source_node = modified_nodes['source'][0]
        source_node_instance = modified_node_instances['source'][0]

        # assert there are 2 relationships total
        self.assertEquals(1, len(source_node.relationships))
        self.assertEquals(1, len(source_node_instance.relationships))

        # check the relationship between site3 and site1 is intact
        self._assert_relationship(
                source_node_instance.relationships,
                target='site1',
                expected_type='cloudify.relationships.connected_to')

        # check the relationship between site3 and site2 was deleted
        self._assert_relationship(
                source_node_instance.relationships,
                target='site2',
                expected_type='new_relationship_type',
                exists=False)

        # check all operation have been executed
        self.assertDictContainsSubset(
                {'target_ops_counter': '1'},
                target_node_instance['runtime_properties']
        )

    def test_remove_workflow(self):
        workflow_id = 'my_custom_workflow'

        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('remove_workflow')
        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.remove(
                dep_update.id,
                entity_type='workflow',
                entity_id='workflows:my_custom_workflow')

        self.client.deployment_updates.commit(dep_update.id)

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        self.assertRaisesRegexp(CloudifyClientError,
                                'Workflow {0} does not exist in deployment {1}'
                                .format(workflow_id, deployment.id),
                                callable_obj=self.client.executions.start,
                                deployment_id=deployment.id,
                                workflow_id=workflow_id,
                                parameters={'node_id': 'site1'})

        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertNotIn('my_custom_workflow',
                         [w['name'] for w in deployment.workflows])

    def test_remove_relationship_operation(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_relationship_operation')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'target': 'site1',
                     'source': 'site2'})

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.remove(
                dep_update.id,
                entity_type='operation',
                entity_id='nodes:site2:relationships:[0]:source_operations:'
                          'cloudify.interfaces.relationship_lifecycle.'
                          'establish'
        )
        self.client.deployment_updates.remove(
                dep_update.id,
                entity_type='operation',
                entity_id='nodes:site2:relationships:[0]:source_operations:'
                          'establish'
        )

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'target': 'site1',
                     'source': 'site2'})

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['target', 'source'],
                excluded_items=['relationships']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['target', 'source'],
                excluded_items=['relationships']
        )

        # Check that there is only 1 from each
        self.assertEquals(1, len(modified_nodes['target']))
        self.assertEquals(1, len(modified_node_instances['target']))
        self.assertEquals(1, len(modified_nodes['source']))
        self.assertEquals(1, len(modified_node_instances['source']))

        # get the nodes and node instances
        source_node = modified_nodes['source'][0]
        source_node_instance = modified_node_instances['source'][0]

        # assert there are 0 relationships
        self.assertEquals(1, len(source_node.relationships))
        self.assertEquals(1, len(source_node_instance.relationships))

        # check the new relationship between site2 and site1 is in place
        self._assert_relationship(
                source_node_instance.relationships,
                target='site1',
                expected_type='new_relationship_type')
        self._assert_relationship(
                source_node.relationships,
                target='site1',
                expected_type='new_relationship_type')

        # check all operation have been executed
        source_operations = \
            source_node['relationships'][0]['source_operations']
        operation_template = \
            no_op_operation('cloudify.interfaces.'
                            'relationship_lifecycle.establish')
        self.assertDictEqual(
                operation_template,
                source_operations['cloudify.interfaces.'
                                  'relationship_lifecycle.establish'])

    def test_remove_property(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('remove_property')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'affected_node': 'site1'})
        base_node = base_nodes['affected_node'][0]

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.remove(
                dep_update.id,
                entity_type='property',
                entity_id='nodes:site1:properties:ip')

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'affected_node': 'site1'})
        modified_node = modified_nodes['affected_node'][0]

        removed_property = modified_node['properties'].get('ip')
        self.assertIsNone(removed_property)
        # assert nothing else changed
        self._assert_equal_dicts(base_node['properties'],
                                 modified_node['properties'],
                                 excluded_items=['ip'])

    def test_remove_output(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('remove_output')
        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.remove(
                dep_update.id,
                entity_type='output',
                entity_id='outputs:custom_output')

        self.client.deployment_updates.commit(dep_update.id)

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertNotIn('custom_output', deployment.outputs)


class TestDeploymentUpdateModification(DeploymentUpdateBase):

    def test_modify_node_operation(self):
        """
        The test sequence is as follows:
        The stop operation is set through the base blueprint to increment
        source_ops runtime_property
        1. execute the stop operation.
        2. check whether the increment indeed occur (i.e. source_ops=1).
        3. create a step which modified the the inputs field of the operation
        from increment to decrement and execute deployment update commit.
        4. execute the stop operation again.
        5. check if the source_ops is now 0.
        :return:
        """
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path(
                    'modify_node_operation')

        # Execute the newly modified operation
        self.client.executions.start(
                deployment.id,
                'execute_operation',
                parameters={
                    'operation': 'cloudify.interfaces.lifecycle.stop'
                }
        )
        self._wait_for_execution_to_terminate(deployment.id,
                                              'execute_operation')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id, {'modified': 'site1'})

        self.assertDictContainsSubset(
                {'source_ops_counter': '1'},
                base_node_instances['modified'][0]['runtime_properties']
        )

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.modify(
                dep_update.id,
                entity_type='operation',
                entity_id='nodes:site1:operations:'
                          'cloudify.interfaces.lifecycle.stop:inputs')

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        # assert nothing changed except for plugins and operations
        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id, {'modified': 'site1'})

        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['modified'],
                excluded_items=['operations']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['modified']
        )

        # Execute the newly modified operation
        self.client.executions.start(
                deployment.id,
                'execute_operation',
                parameters={
                    'operation': 'cloudify.interfaces.lifecycle.stop'
                }
        )
        self._wait_for_execution_to_terminate(deployment.id,
                                              'execute_operation')

        # Check again for the nodes and node instances and check
        # their runtime properties
        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id, {'modified': 'site1'})

        self.assertEqual(len(modified_nodes['modified']), 1)
        modified_node = modified_nodes['modified'][0]
        self.assertEqual(len(modified_node_instances['modified']), 1)
        modified_node_instance = modified_node_instances['modified'][0]

        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['modified'],
                excluded_items=['operations']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['modified'],
                excluded_items=['runtime_properties']
        )

        affected_lifecycle_operation = modified_node['operations'].get(
                'cloudify.interfaces.lifecycle.create')
        self.assertIsNotNone(affected_lifecycle_operation)

        self.assertDictContainsSubset(
                {'source_ops_counter': '0'},
                modified_node_instance['runtime_properties']
        )

    def test_modify_relationship_operation(self):
        """
        In this test the script_path of the operation is modified from
        increment to decrement. this is tested on storage level (no operation
        is executed since this is a relationship operation, and currently we
        have no mechanism in place to execute relationship operation.
        :return:
        """
        deployment, modified_bp_path = self._deploy_and_get_modified_bp_path(
                'modify_relationship_operation')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'target': 'site1',
                     'source': 'site2'})

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.modify(
                dep_update.id,
                entity_type='operation',
                entity_id='nodes:site2:relationships:[0]:source_operations:'
                          'cloudify.interfaces.relationship_lifecycle.'
                          'establish:inputs:script_path'
        )

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'target': 'site1',
                     'source': 'site2'})

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['target', 'source'],
                excluded_items=['relationships']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['target', 'source'],
                excluded_items=['relationships']
        )

        # Check that there is only 1 from each
        self.assertEquals(1, len(modified_nodes['target']))
        self.assertEquals(1, len(modified_node_instances['target']))
        self.assertEquals(1, len(modified_nodes['source']))
        self.assertEquals(1, len(modified_node_instances['source']))

        # get the nodes and node instances
        source_node = modified_nodes['source'][0]
        source_node_instance = modified_node_instances['source'][0]

        # assert there are 0 relationships
        self.assertEquals(1, len(source_node.relationships))
        self.assertEquals(1, len(source_node_instance.relationships))

        # check the new relationship between site2 and site1 is in place
        self._assert_relationship(
                source_node_instance.relationships,
                target='site1',
                expected_type='new_relationship_type')
        self._assert_relationship(
                source_node.relationships,
                target='site1',
                expected_type='new_relationship_type')

        dict_to_check = self._create_dict(['inputs', 'script_path',
                                           'decrement.sh'])

        # check all operation have been executed
        source_operations = \
            source_node['relationships'][0]['source_operations']
        self.assertDictContainsSubset(
                dict_to_check,
                source_operations
                ['cloudify.interfaces.relationship_lifecycle.establish']
        )

    def test_modify_property(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_property')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'affected_node': 'site1'})
        base_node = base_nodes['affected_node'][0]

        base_properties = base_node['properties']
        modified_property = \
            base_properties.get('custom_prop', {}).get('inner_prop')
        self.assertEqual(modified_property, 1)

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.modify(
                dep_update.id,
                entity_type='property',
                entity_id='nodes:site1:properties:custom_prop:inner_prop')

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'affected_node': 'site1'})
        modified_node = modified_nodes['affected_node'][0]
        modified_properties = modified_node['properties']
        modified_property = \
            modified_properties.get('custom_prop', {}).get('inner_prop')
        self.assertIsNotNone(modified_property)
        self.assertEqual(modified_property, 2)

        # assert nothing else changed
        self._assert_equal_dicts(base_node['properties'],
                                 modified_node['properties'],
                                 excluded_items=['custom_prop'])

    def test_modify_workflow(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_workflow')
        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.modify(
                dep_update.id,
                entity_type='workflow',
                entity_id='workflows:my_custom_workflow')

        self.client.deployment_updates.commit(dep_update.id)

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id,
                                              'update')

        self.client.executions.start(dep_update.deployment_id,
                                     workflow_id='my_custom_workflow',
                                     parameters={'node_id': 'site1'})

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id,
                                              'my_custom_workflow')
        affected_node = \
            self.client.node_instances.list(dep_update.deployment_id,
                                            'site1')
        self.assertEqual(len(affected_node), 6)
        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertIn('my_custom_workflow',
                      [w['name'] for w in deployment.workflows])

    def test_modify_output(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_output')

        deployment = self.client.deployments.get(deployment.id)
        self.assertDictContainsSubset({'custom_output': {'value': 0}},
                                      deployment.outputs)

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.modify(
                dep_update.id,
                entity_type='output',
                entity_id='outputs:custom_output')

        self.client.deployment_updates.commit(dep_update.id)

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertDictContainsSubset({'custom_output': {'value': 1}},
                                      deployment.outputs)


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
            \         ^
             \       /
              ->site3
        :return:
        """
        deployment, modified_bp_path = self._deploy_and_get_modified_bp_path(
                'add_node_and_relationship')

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(deployment.id,
                                                    {'stagnant': 'site1',
                                                     'added_relationships':
                                                         'site2'})

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='node',
                entity_id='nodes:site3')

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='relationship',
                entity_id='nodes:site2:relationships:[1]'
        )

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(deployment.id,
                                                    {'added_relationship':
                                                     'site2'})

        # check all operation have been executed
        self.assertDictContainsSubset(
                {'source_ops_counter': '3'},
                modified_node_instances['added_relationship'][0]
                ['runtime_properties']
        )

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        # Get all related and affected nodes and node instances

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(deployment.id,
                                                    {'stagnant': 'site1',
                                                     'added_relationships':
                                                         'site2',
                                                     'new': 'site3'})

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['stagnant', 'added_relationships', 'new'],
                excluded_items=['runtime_properties',
                                'plugins',
                                'relationships']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['stagnant', 'added_relationships', 'new'],
                excluded_items=['runtime_properties', 'relationships']
        )

        # Check that there is only 1 from each
        self.assertEquals(1, len(modified_nodes['stagnant']))
        self.assertEquals(1, len(modified_node_instances['stagnant']))
        self.assertEquals(1, len(modified_nodes['added_relationships']))
        self.assertEquals(1,
                          len(modified_node_instances['added_relationships']))
        self.assertEquals(1, len(modified_nodes['new']))
        self.assertEquals(1, len(modified_node_instances['new']))

        # get the nodes and node instances
        added_relationship_node_instance = \
            modified_node_instances['added_relationships'][0]
        new_node = modified_nodes['new'][0]
        new_node_instance = modified_node_instances['new'][0]

        # assert there are 2 relationships total
        self.assertEquals(1, len(new_node.relationships))
        self.assertEquals(2,
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
        self.assertDictContainsSubset(
                {'source_ops_counter': '4'},
                added_relationship_node_instance['runtime_properties']
        )

        self.assertDictContainsSubset(
                {'source_ops_counter': '3'},
                new_node_instance['runtime_properties']
        )

    def test_add_and_override_resource(self):
        """
        In order to test the resources mechanism
         1. we first upload the local_modification resource which increments
         the source_ops_counter each relationships operation executed between
         site2->site1
         2. we also upload the increment resource for future use.

            after this step we check that indeed the
            site2.source_ops_counter == 3

         2. after uploading the new blueprint (with its resources), the
         local_modification script decrements the same counter for each
         relationship operation executed between site2->site3 (since pre
         and post configure already ran, it should be ran only once)

         3. we set the increment script to be used for each operation between
         site3->site1

            after both of these steps we check that indeed the
            site2.source_ops_counter == 2
            and
            site3.source_ops_counter == 3
        :return:
        """
        deployment, modified_bp_path = self._deploy_and_get_modified_bp_path(
                'add_and_override_resource')

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='node',
                entity_id='nodes:site3')

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='relationship',
                entity_id='nodes:site2:relationships:[1]'
        )

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'added_relationship': 'site2'}
            )

        # check all operation have been executed
        self.assertDictContainsSubset(
                {'source_ops_counter': '3'},
                base_node_instances['added_relationship'][0]
                ['runtime_properties']
        )

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        # Get all related and affected nodes and node instances

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'stagnant': 'site1',
                     'added_relationships': 'site2',
                     'new': 'site3'}
            )

        # get the nodes and node instances
        added_relationship_node_instance = \
            modified_node_instances['added_relationships'][0]
        new_node_instance = modified_node_instances['new'][0]

        # check all operation have been executed.
        # source_ops_counter was increased for each operation between site2 and
        # site1, and another site2.source_ops_counter should have
        # decreased once because of the resource override
        self.assertDictContainsSubset(
                {'source_ops_counter': '2'},
                added_relationship_node_instance['runtime_properties']
        )

        self.assertDictContainsSubset(
                {'source_ops_counter': '3'},
                new_node_instance['runtime_properties']
        )

    def test_use_new_and_old_inputs(self):
        """
        We first provide the os_family_input at the initial deployment
        creation. Then we add the ip_input. we use both only in the final
        blueprint. Note that it's not possible to overwrite inputs (and it
        wasn't tested.
        :return:
        """
        deployment, modified_bp_path = self._deploy_and_get_modified_bp_path(
                'use_new_and_old_inputs',
                inputs={'os_family_input': 'windows'}
        )

        base_nodes, base_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'affected_node': 'site1'})
        base_node = base_nodes['affected_node'][0]

        dep_update = \
            self.client.deployment_updates.stage(
                    deployment.id,
                    modified_bp_path,
                    inputs={'ip_input': '1.1.1.1'}
            )

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='property',
                entity_id='nodes:site1:properties:os_family')

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='property',
                entity_id='nodes:site1:properties:ip')

        self.client.deployment_updates.add(
            dep_update.id,
            entity_type='output',
            entity_id='outputs:ip_output'
        )

        self.client.deployment_updates.commit(dep_update.id)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_committed_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._get_nodes_and_node_instances_dict(
                    deployment.id,
                    {'affected_node': 'site1'})
        modified_node = modified_nodes['affected_node'][0]

        added_property = modified_node['properties']
        self.assertIsNotNone(added_property.get('ip'))
        self.assertIsNotNone(added_property.get('os_family'))
        self.assertEqual(added_property['ip'], '1.1.1.1')
        self.assertEqual(added_property['os_family'], 'windows')

        # Checking that get_property works correctly
        output_property = self.client.deployments.get(deployment.id).outputs
        self.assertDictContainsSubset({'ip_output': {'value': '1.1.1.1'}},
                                      output_property)

        # assert nothing else changed
        self._assert_equal_dicts(base_node['properties'],
                                 modified_node['properties'],
                                 excluded_items=['ip', 'os_family'])

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

from manager_rest.models import Execution
from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import tar_blueprint

blueprints_base_path = 'dsl/deployment_update'


class TestDeploymentUpdate(TestCase):

    def _wait_for_execution(self, execution, timeout=900):
        # Poll for execution status until execution ends
        deadline = time.time() + timeout
        while True:
            if time.time() > deadline:
                raise Exception(
                    'execution of operation {0} for deployment {1} timed out'.
                    format(execution.workflow_id, execution.deployment_id))

            execution = self.client.executions.get(execution.id)
            if execution.status in Execution.END_STATES:
                return execution
            time.sleep(3)

    @staticmethod
    def assert_equal_dictionaries(self, d1, d2, exceptions=()):
        for k, v in d1.iteritems():
            if k not in exceptions:
                self.assertEquals(d2[k], v,
                                  'The nodes differed on {0}. {1}!={2}'
                                  .format(k, d1[k], d2[k]))

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

    def _deploy_and_get_modified_bp_path(self, bp_name):

        base_bp = '{0}_base.yaml'.format(bp_name)
        modified_bp = '{0}_modification.yaml'.format(bp_name)

        base_bp_path = \
            resource(os.path.join(blueprints_base_path, base_bp))
        deployment, _ = deploy(base_bp_path)
        modified_bp_path = \
            resource(os.path.join(blueprints_base_path, modified_bp))

        return deployment, modified_bp_path

    def test_add_relationship(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('dep_up_add_relationship')

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='relationship',
                entity_id='site2:site1')

        self.client.deployment_updates.commit(dep_update.id)

        # assert that 'update' workflow was executed
        executions = \
            self.client.executions.list(deployment_id=deployment.id,
                                        workflow_id='update')
        execution = self._wait_for_execution(executions[0])
        self.assertEquals('terminated', execution['status'],
                          execution.error)

        # Get all related and affected nodes and node instances
        related_nodes = \
            self.client.nodes.list(deployment_id=deployment.id,
                                   node_id='site0')
        related_node_instances = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site0')
        target_nodes = self.client.nodes.list(deployment_id=deployment.id,
                                              node_id='site1')
        target_node_instances = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site1')
        source_nodes = \
            self.client.nodes.list(deployment_id=deployment.id,
                                   node_id='site2')
        source_node_instances = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site2')

        # Check that there is only 1 from each
        self.assertEquals(1, len(related_nodes))
        self.assertEquals(1, len(related_node_instances))
        self.assertEquals(1, len(target_nodes))
        self.assertEquals(1, len(target_node_instances))
        self.assertEquals(1, len(source_nodes))
        self.assertEquals(1, len(source_node_instances))

        # get the nodes and node instances
        # TODO: check that the other nodes/node_instances haven't changed
        related_node = related_nodes[0]                                         # NOQA
        related_node_instance = related_node_instances[0]                       # NOQA
        target_node = target_nodes[0]                                           # NOQA
        target_node_instance = target_node_instances[0]
        source_node = source_nodes[0]
        source_node_instance = source_node_instances[0]

        # assert there are 2 relationships total
        self.assertEquals(2, len(source_node.relationships))
        self.assertEquals(2, len(source_node_instance.relationships))

        # check the relationship between site2 and site0 is intact
        self._assert_relationship(
                source_node_instance.relationships,
                target='site0',
                expected_type='cloudify.relationships.connected_to')
        self._assert_relationship(
                source_node.relationships,
                target='site0',
                expected_type='cloudify.relationships.connected_to')

        # check the new relationship between site2 and site1 is in place
        self._assert_relationship(
                source_node_instance.relationships,
                target='site1',
                expected_type='added_relationships')
        self._assert_relationship(
                source_node.relationships,
                target='site1',
                expected_type='added_relationships')

        # check all operation have been executed
        self.assertDictContainsSubset(
                {'source_ops_counter': '1'},
                source_node_instance['runtime_properties']
        )

        self.assertDictContainsSubset(
                {'target_ops_counter': '1'},
                target_node_instance['runtime_properties']
        )

    def test_remove_relationship(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('dep_up_remove_relationship')

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.remove(
                dep_update.id,
                entity_type='relationship',
                entity_id='site2:site1')

        self.client.deployment_updates.commit(dep_update.id)

        # assert that 'update' workflow was executed
        executions = \
            self.client.executions.list(deployment_id=deployment.id,
                                        workflow_id='update')
        execution = self._wait_for_execution(executions[0])
        self.assertEquals('terminated', execution['status'],
                          execution.error)

        # Get all related and affected nodes and node instances
        related_nodes = \
            self.client.nodes.list(deployment_id=deployment.id,
                                   node_id='site0')
        related_node_instances = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site0')
        target_nodes = self.client.nodes.list(deployment_id=deployment.id,
                                              node_id='site1')
        target_node_instances = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site1')
        source_nodes = \
            self.client.nodes.list(deployment_id=deployment.id,
                                   node_id='site2')
        source_node_instances = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site2')

        # Check that there is only 1 from each
        self.assertEquals(1, len(related_nodes))
        self.assertEquals(1, len(related_node_instances))
        self.assertEquals(1, len(target_nodes))
        self.assertEquals(1, len(target_node_instances))
        self.assertEquals(1, len(source_nodes))
        self.assertEquals(1, len(source_node_instances))

        # get the nodes and node instances
        # TODO: check that the other nodes/node_instances haven't changed
        related_node = related_nodes[0]                                         # NOQA
        related_node_instance = related_node_instances[0]                       # NOQA
        target_node = target_nodes[0]                                           # NOQA
        target_node_instance = target_node_instances[0]
        source_node = source_nodes[0]
        source_node_instance = source_node_instances[0]

        # assert there are 2 relationships total
        self.assertEquals(1, len(source_node.relationships))
        self.assertEquals(1, len(source_node_instance.relationships))

        # check the relationship between site2 and site0 is intact
        self._assert_relationship(
                source_node_instance.relationships,
                target='site0',
                expected_type='cloudify.relationships.connected_to')

        # check the relationship between site2 and site1 was deleted
        self._assert_relationship(
                source_node_instance.relationships,
                target='site1',
                expected_type='added_relationships',
                exists=False)

        # check all operation have been executed
        self.assertDictContainsSubset(
                {'target_ops_counter': '1'},
                target_node_instance['runtime_properties']
        )

    def test_remove_node(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('dep_up_remove_node')

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)
        self.client.deployment_updates.remove(
                dep_update.id,
                entity_type='node',
                entity_id='site2')

        self.client.deployment_updates.commit(dep_update.id)

        # assert that 'update' workflow was executed
        executions = \
            self.client.executions.list(deployment_id=deployment.id,
                                        workflow_id='update')
        execution = self._wait_for_execution(executions[0])
        self.assertEquals('terminated', execution['status'],
                          execution.error)

        remove_related_node = \
            self.client.nodes.list(deployment_id=deployment.id,
                                   node_id='site1')
        remove_related_node_instances = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site1')

        removed_nodes = self.client.nodes.list(deployment_id=deployment.id,
                                               node_id='site2')
        removed_node_instnaces = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site2')

        # assert that node and node instance were removed from storage
        self.assertEquals(0, len(removed_nodes))
        self.assertEquals(0, len(removed_node_instnaces))

        # assert relationship target remained intact
        self.assertEquals(1, len(remove_related_node))
        self.assertEquals(1, len(remove_related_node_instances))

        # assert all operations in 'update' ('install') workflow
        # are executed by making them increment a runtime property
        remove_related_instance = remove_related_node_instances[0]
        self.assertDictContainsSubset(
                {'target_ops_counter': '1'},
                remove_related_instance['runtime_properties']
        )

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
            self._deploy_and_get_modified_bp_path('dep_up_add_node')

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

            self.client.deployment_updates.add(dep_update.id,
                                               entity_type='node',
                                               entity_id='site2')
            self.client.deployment_updates.commit(dep_update.id)

            # assert that 'update' workflow was executed
            executions = \
                self.client.executions.list(deployment_id=deployment.id,
                                            workflow_id='update')
            execution = self._wait_for_execution(executions[0])
            self.assertEquals('terminated', execution['status'],
                              execution.error)

            added_nodes = self.client.nodes.list(deployment_id=deployment.id,
                                                 node_id='site2')
            added_instances = \
                self.client.node_instances.list(deployment_id=deployment.id,
                                                node_id='site2')

            # assert that node and node instance were added to storage
            self.assertEquals(1, len(added_nodes))
            self.assertEquals(1, len(added_instances))

            # assert that node has a relationship
            node = added_nodes[0]
            self.assertEquals(1, len(node.relationships))
            self._assert_relationship(
                    node.relationships,
                    target='site1',
                    expected_type='cloudify.relationships.contained_in')
            self.assertEquals(node.type, 'cloudify.nodes.WebServer')

            # assert that node instance has a relationship
            added_instance = added_instances[0]
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
                    'dep_up_add_node_and_relationship')

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 modified_bp_path)

        self.client.deployment_updates.add(
                dep_update.id,
                entity_type='node',
                entity_id='site3')

        self.client.deployment_updates.add(
            dep_update.id,
            entity_type='relationship',
            entity_id='site2:site3'
        )

        added_relationship_node_instances = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site2')
        added_relationship_node_instance = added_relationship_node_instances[0]
        # check all operation have been executed
        self.assertDictContainsSubset(
                {'source_ops_counter': '3'},
                added_relationship_node_instance['runtime_properties']
        )

        self.client.deployment_updates.commit(dep_update.id)

        # assert that 'update' workflow was executed
        executions = \
            self.client.executions.list(deployment_id=deployment.id,
                                        workflow_id='update')
        execution = self._wait_for_execution(executions[0])
        self.assertEquals('terminated', execution['status'],
                          execution.error)

        # Get all related and affected nodes and node instances
        stagnant_nodes = \
            self.client.nodes.list(deployment_id=deployment.id,
                                   node_id='site1')
        stagnant_node_instances = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site1')

        added_relationship_nodes = \
            self.client.nodes.list(deployment_id=deployment.id,
                                   node_id='site2')
        added_relationship_node_instances = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site2')
        new_nodes = \
            self.client.nodes.list(deployment_id=deployment.id,
                                   node_id='site3')
        new_node_instances = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site3')

        # Check that there is only 1 from each
        self.assertEquals(1, len(stagnant_nodes))
        self.assertEquals(1, len(stagnant_node_instances))
        self.assertEquals(1, len(added_relationship_nodes))
        self.assertEquals(1, len(added_relationship_node_instances))
        self.assertEquals(1, len(new_nodes))
        self.assertEquals(1, len(new_node_instances))

        # get the nodes and node instances
        # TODO: check that the other nodes/node_instances haven't changed
        added_relationship_node_instance = added_relationship_node_instances[0]
        new_node = new_nodes[0]
        new_node_instance = new_node_instances[0]

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

        # check all operation have been executed
        self.assertDictContainsSubset(
                {'source_ops_counter': '4'},
                added_relationship_node_instance['runtime_properties']
        )

        self.assertDictContainsSubset(
                {'source_ops_counter': '3'},
                new_node_instance['runtime_properties']
        )

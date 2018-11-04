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
import time

from cloudify.models_states import ExecutionState
from manager_rest.deployment_update.constants import STATES

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource


blueprints_base_path = 'dsl/deployment_update'


class TimeoutException(Exception):
    pass


class DeploymentUpdateOldBase(AgentlessTestCase):

    def _wait_for(
            self,
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
                raise TimeoutException(msg)
            value = callable_obj(callable_obj_key)
            if test_condition(getattr(value, value_attr), test_value):
                return value
            time.sleep(3)

    def _wait_for_successful_state(self, depup_id):
        error_msg = 'deployment update {0} failed to commit'.format(depup_id)
        return self._wait_for(self.client.deployment_updates.get,
                              depup_id,
                              'state',
                              STATES.SUCCESSFUL,
                              lambda x, y: x == y,
                              error_msg)

    def _wait_for_execution(self, execution, timeout=900):
        # Poll for execution status until execution ends
        error_msg = 'execution of operation {0} for deployment {1} timed out' \
            .format(execution.workflow_id, execution.deployment_id)
        return self._wait_for(self.client.executions.get,
                              execution.id,
                              'status',
                              ExecutionState.END_STATES,
                              lambda x, y: x in y,
                              error_msg,
                              timeout)

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

    def _deploy_and_get_modified_bp_path(self,
                                         test_name,
                                         inputs=None,
                                         deployment_id=None):
        base_bp_path, modified_bp_path = \
            self._get_base_and_modified_bp_path(test_name)

        deployment, _ = self.deploy_application(
                base_bp_path,
                inputs=inputs,
                deployment_id=deployment_id)

        return deployment, modified_bp_path

    def _get_base_and_modified_bp_path(self, test_name):
        base_dir = os.path.join(test_name, 'base')
        modified_dir = os.path.join(test_name, 'modification')
        base_bp = '{0}_base.yaml'.format(test_name)
        modified_bp = '{0}_modification.yaml'.format(test_name)

        base_bp_path = self._get_blueprint_path(base_dir, base_bp)
        modified_bp_path = self._get_blueprint_path(modified_dir, modified_bp)
        return base_bp_path, modified_bp_path

    def _get_blueprint_path(self, blueprint_folder, blueprint_file):
        return resource(
                os.path.join(blueprints_base_path,
                             blueprint_folder,
                             blueprint_file))

    def _wait_for_execution_to_terminate(self, deployment_id, workflow_id):
        # wait for 'update' workflow to finish
        executions = \
            self.client.executions.list(deployment_id=deployment_id,
                                        workflow_id=workflow_id)
        for execution in executions:
            self._wait_for_execution(execution)

    def _map_node_and_node_instances(self, deployment_id, dct):
        nodes_dct = {k: [] for k, _ in dct.iteritems()}
        node_instances_dct = {k: [] for k, _ in dct.iteritems()}

        for k, v in dct.iteritems():
            nodes = list(self.client.nodes.list(
                deployment_id=deployment_id,
                node_id=dct[k]
            ))
            node_instances = \
                list(self.client.node_instances.list(
                    deployment_id=deployment_id,
                    node_id=dct[k]
                ))
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
                # Assuming here that only node instances have a version
                # in their dict, and so `version_changed` is only applicable
                # in the cases where we're comparing node instances
                if k == 'version':
                    self.assertGreaterEqual(d2.get(k, None), v,
                                            'New version should be greater '
                                            ' or equal to the old version. '
                                            'Old: {0}, new: {1}'
                                            .format(d1[k], d2[k]))
                else:
                    self.assertEquals(d2.get(k, None), v,
                                      '{0} has changed on {1}. {2}!={3}'
                                      .format(d1, k, d1[k], d2[k]))

    def _create_dict(self, path):
        if len(path) == 1:
            return path[0]
        else:
            return {path[0]: self._create_dict(path[1:])}

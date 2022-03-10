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


import uuid
import dateutil.parser

import pytest

from cloudify_rest_client.deployment_modifications import (
    DeploymentModification)

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_deployments


@pytest.mark.usefixtures('testmockoperations_plugin')
@pytest.mark.usefixtures('mock_workflows_plugin')
class TestDeploymentModification(AgentlessTestCase):

    def test_modification_operations(self):
        dsl_path = resource("dsl/deployment_modification_operations.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        deployment_id = deployment.id
        self.execute_workflow('deployment_modification', deployment_id)
        invocations = self._get_operation_invocations(deployment_id)
        self.assertEqual(1, len([i for i in invocations
                                 if i['operation'] == 'create']))
        self.assertEqual(2, len([i for i in invocations
                                 if i['operation'] == 'preconfigure']))
        self.assertEqual(2, len([i for i in invocations
                                 if i['operation'] == 'preconfigure']))
        configure_invocations = [i for i in invocations
                                 if i['operation'] == 'configure']
        self.assertEqual(1, len(configure_invocations))
        self.assertEqual(1, len(configure_invocations[0]['target_ids']))
        start_invocations = [i for i in invocations
                             if i['operation'] == 'start']
        self.assertEqual(1, len(start_invocations))
        self.assertEqual(2, len(start_invocations[0]['target_ids']))

    def test_deployment_modification_add_compute(self):
        nodes = {'compute': {'instances': 2}}
        return self._test_deployment_modification(
            modification_type='added',
            modified_nodes=nodes,
            expected_compute={'existence': 1,
                              'modification': 1,
                              'relationships': 0,
                              'total_relationships': 0},
            expected_db={'existence': 1,
                         'modification': 1,
                         'relationships': 1,
                         'total_relationships': 1},
            expected_webserver={'existence': 1,
                                'modification': 0,
                                'relationships': 1,
                                'total_relationships': 2},
            expected_total=5)

    def test_deployment_modification_add_db(self):
        nodes = {'db': {'instances': 2}}
        self._test_deployment_modification(
            modification_type='added',
            modified_nodes=nodes,
            expected_compute={'existence': 1,
                              'modification': 0,
                              'relationships': 0,
                              'total_relationships': 0},
            expected_db={'existence': 1,
                         'modification': 1,
                         'relationships': 1,
                         'total_relationships': 1},
            expected_webserver={'existence': 1,
                                'modification': 0,
                                'relationships': 1,
                                'total_relationships': 2},
            expected_total=4)

    def test_deployment_modification_add_webserver(self):
        nodes = {'webserver': {'instances': 2}}
        self._test_deployment_modification(
            modification_type='added',
            modified_nodes=nodes,
            expected_compute={'existence': 0,
                              'modification': 0,
                              'relationships': 0,
                              'total_relationships': 0},
            expected_db={'existence': 1,
                         'modification': 0,
                         'relationships': 0,
                         'total_relationships': 1},
            expected_webserver={'existence': 1,
                                'modification': 1,
                                'relationships': 1,
                                'total_relationships': 1},
            expected_total=4)

    def test_deployment_modification_remove_compute(self):
        deployment_id = self.test_deployment_modification_add_compute()
        self._clear_state(deployment_id)
        nodes = {'compute': {'instances': 1}}
        self._test_deployment_modification(
            deployment_id=deployment_id,
            modification_type='removed',
            modified_nodes=nodes,
            expected_compute={'existence': 0,
                              'modification': 0,
                              'relationships': 0,
                              'total_relationships': 0},
            expected_db={'existence': 0,
                         'modification': 0,
                         'relationships': 0,
                         'total_relationships': 1},
            expected_webserver={'existence': 1,
                                'modification': 0,
                                'relationships': 1,
                                'total_relationships': 1},
            expected_total=3)

    def test_deployment_modification_add_compute_rollback(self):
        nodes = {'compute': {'instances': 2}}
        return self._test_deployment_modification(
            modification_type='added',
            modified_nodes=nodes,
            expected_compute={'existence': 0,
                              'modification': 0,
                              'relationships': 0,
                              'total_relationships': 0},
            expected_db={'existence': 0,
                         'modification': 0,
                         'relationships': 0,
                         'total_relationships': 1},
            expected_webserver={'existence': 0,
                                'modification': 0,
                                'relationships': 0,
                                'total_relationships': 1},
            expected_total=3,
            rollback=True)

    def _test_deployment_modification(self,
                                      modified_nodes,
                                      expected_compute,
                                      expected_db,
                                      expected_webserver,
                                      modification_type,
                                      expected_total,
                                      deployment_id=None,
                                      rollback=False):
        if not deployment_id:
            dsl_path = resource("dsl/deployment_modification.yaml")
            test_id = 'i{0}'.format(uuid.uuid4())
            deployment, _ = self.deploy_application(
                    dsl_path,
                    deployment_id=test_id,
                    blueprint_id='b_{0}'.format(test_id))
            deployment_id = deployment.id

        nodes_before_modification = {
            node.id: node for node in
            self.client.nodes.list(deployment_id=deployment_id)
        }

        before_modifications = self.client.deployment_modifications.list(
            deployment_id)

        workflow_id = 'deployment_modification_{0}'.format(
            'rollback' if rollback else 'finish')

        execution = self.execute_workflow(
            workflow_id, deployment_id,
            parameters={'nodes': modified_nodes})

        after_modifications = self.client.deployment_modifications.list(
            deployment_id)

        new_modifications = [
            m for m in after_modifications
            if m.id not in [m2.id for m2 in before_modifications]]
        self.assertEqual(len(new_modifications), 1)
        modification = list(new_modifications)[0]
        self.assertEqual(self.client.deployment_modifications.get(
            modification.id), modification)

        expected_status = DeploymentModification.ROLLEDBACK if rollback \
            else DeploymentModification.FINISHED
        self.assertEqual(modification.status, expected_status)
        self.assertEqual(modification.deployment_id, deployment_id)
        self.assertEqual(modification.modified_nodes, modified_nodes)
        self._assertDictContainsSubset({
            'workflow_id': workflow_id,
            'execution_id': execution.id,
            'deployment_id': deployment_id,
            'blueprint_id': 'b_{0}'.format(deployment_id)},
            modification.context)
        created_at = dateutil.parser.parse(modification.created_at)
        ended_at = dateutil.parser.parse(modification.ended_at)
        self.assertTrue(created_at <= ended_at)
        for node_id, modified_node in modified_nodes.items():
            node = self.client.nodes.get(deployment_id, node_id)
            if rollback:
                self.assertEqual(
                    node.planned_number_of_instances,
                    nodes_before_modification[
                        node.id].planned_number_of_instances)
                self.assertEqual(
                    node.number_of_instances,
                    nodes_before_modification[
                        node.id].number_of_instances)
            else:
                self.assertEqual(node.planned_number_of_instances,
                                 modified_node['instances'])
                self.assertEqual(node.number_of_instances,
                                 modified_node['instances'])

        state = self.get_runtime_property(deployment_id, 'state')

        compute_instances = self._get_instances(state, 'compute')
        db_instances = self._get_instances(state, 'db')
        webserver_instances = self._get_instances(state, 'webserver')

        # existence
        self.assertEqual(expected_compute['existence'], len(compute_instances))
        self.assertEqual(expected_db['existence'], len(db_instances))
        self.assertEqual(expected_webserver['existence'],
                         len(webserver_instances))

        # modification
        self.assertEqual(expected_compute['modification'],
                         len([i for i in compute_instances
                             if i['modification'] == modification_type]))
        self.assertEqual(expected_db['modification'],
                         len([i for i in db_instances
                             if i['modification'] == modification_type]))
        self.assertEqual(expected_webserver['modification'],
                         len([i for i in webserver_instances
                             if i['modification'] == modification_type]))

        # relationships
        if compute_instances:
            self.assertEqual(expected_compute['relationships'],
                             len(compute_instances[0]['relationships']))
        if db_instances:
            self.assertEqual(expected_db['relationships'],
                             len(db_instances[0]['relationships']))
        if webserver_instances:
            self.assertEqual(expected_webserver['relationships'],
                             len(webserver_instances[0]['relationships']))

        node_instances = self.client.node_instances.list(
            deployment_id=deployment_id
        )
        self.assertEqual(expected_total, len(node_instances))
        for node_id, modification in modified_nodes.items():
            if rollback:
                self.assertEqual(
                    nodes_before_modification[
                        node_id].number_of_instances,
                    self.client.nodes.get(
                        deployment_id, node_id).number_of_instances)
            else:
                self.assertEqual(
                    modification['instances'],
                    self.client.nodes.get(
                        deployment_id, node_id).number_of_instances)
        for node_instance in node_instances:
            relationships_count = len(node_instance.relationships)
            if node_instance.node_id == 'compute':
                self.assertEqual(relationships_count,
                                 expected_compute['total_relationships'])
            if node_instance.node_id == 'db':
                self.assertEqual(relationships_count,
                                 expected_db['total_relationships'])
            if node_instance.node_id == 'webserver':
                self.assertEqual(relationships_count,
                                 expected_webserver['total_relationships'])

        return deployment_id

    @staticmethod
    def _get_instances(state, node_id):
        state_values = [next(iter(i.values())) for i in state]
        return [i for i in state_values if i['node_id'] == node_id]

    def test_group_deployment_modification(self):
        # this test specifically tests elasticsearch's implementation
        # of update_deployment. other features are tested elsewhere.
        deployment = self.deploy(
            resource('dsl/deployment_modification_groups.yaml'))
        modification = self.client.deployment_modifications.start(
            deployment_id=deployment.id,
            nodes={
                'compute_and_ip': {
                    'instances': 2
                }
            })
        self.client.deployment_modifications.finish(modification.id)
        deployment = self.client.deployments.get(deployment.id)
        scaling_group = deployment['scaling_groups']['compute_and_ip']
        self.assertEqual(2, scaling_group['properties']['planned_instances'])
        self.assertEqual(2, scaling_group['properties']['current_instances'])

    def _get_operation_invocations(self, deployment_id):
        invocation_lists = self.get_runtime_property(
            deployment_id, 'mock_operation_invocation')
        invocations = []
        for lst in invocation_lists:
            invocations.extend(lst)
        return invocations

    def _clear_state(self, deployment_id):
        for inst in self.client.node_instances.list(
                deployment_id=deployment_id):
            if 'state' in inst.runtime_properties:
                self.client.node_instances.update(
                    node_instance_id=inst.id,
                    version=inst.version + 1,
                    runtime_properties={'state': {}})

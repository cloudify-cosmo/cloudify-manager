#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
#

from manager_rest.test.attribute import attr

from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test.infrastructure.base_list_test import BaseListTest


@attr(client_min_version=1, client_max_version=1)
class TestResourceListV1(BaseListTest):
    """
    REST list operations have changed in v2. This test class assures v1
    backwards compatibility has been preserved.
    """

    def setUp(self):
        super(TestResourceListV1, self).setUp()
        self._put_n_deployments(id_prefix='test', number_of_deployments=2)
        self.first_blueprint_id = 'test0_blueprint'
        self.first_deployment_id = 'test0_deployment'
        self.sec_blueprint_id = 'test1_blueprint'
        self.sec_deployment_id = 'test1_deployment'

    def test_insecure_endpoints_disabled_by_default(self):
        try:
            self.client.executions.list(deployment_id='111')
        except CloudifyClientError, e:
            self.assertEquals(405, e.status_code)

    def test_insecure_endpoints_enabled(self):
        from manager_rest.config import instance
        try:
            instance.insecure_endpoints_disabled = False
            result = self.client.executions.list(deployment_id='111')
        finally:
            # restore original value
            instance.insecure_endpoints_disabled = True

        # Since there are not events in the test database
        # an empty result is returned
        self.assertEqual(result, ([], 0))

    def test_blueprints_list_no_params(self):
        response = self.client.blueprints.list()
        self.assertEqual(2, len(response), 'expecting 2 blueprint result,'
                                           ' got {0}'.format(len(response)))
        for blueprint in response:
            self.assertIn(blueprint['id'],
                          (self.first_blueprint_id, self.sec_blueprint_id))
            self.assertIsNotNone(blueprint['plan'])

    def test_deployments_list_no_params(self):
        deployments = self.client.deployments.list()
        self.assertEqual(2, len(deployments),
                         'expecting 2 deployment results, got {0}'
                         .format(len(deployments)))

        if deployments[0]['id'] != self.first_deployment_id:
            deployments[0], deployments[1] = deployments[1], deployments[0]

        self.assertEquals(self.first_blueprint_id,
                          deployments[0]['blueprint_id'])
        self.assertEquals(self.sec_blueprint_id,
                          deployments[1]['blueprint_id'])

    def test_nodes_list_no_params(self):
        response = self.client.nodes.list()
        self.assertEqual(4, len(response), 'expecting 4 node results, '
                                           'got {0}'.format(len(response)))
        for node in response:
            self.assertIn(node['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertIn(node['blueprint_id'],
                          (self.first_blueprint_id, self.sec_blueprint_id))

    def test_nodes_list_with_params(self):
        params = {'deployment_id': self.first_deployment_id}
        response = self.client.nodes.list(**params)
        self.assertEqual(2, len(response), 'expecting 1 node result, '
                                           'got {0}'.format(len(response)))
        for node in response:
            self.assertEquals(node['deployment_id'], self.first_deployment_id)
            self.assertEquals(node['blueprint_id'], self.first_blueprint_id)

    def test_executions_list_no_params(self):
        response = self.client.executions.list()
        self.assertEqual(2, len(response), 'expecting 2 executions results, '
                                           'got {0}'.format(len(response)))
        for execution in response:
            self.assertIn(execution['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertIn(execution['blueprint_id'],
                          (self.first_blueprint_id, self.sec_blueprint_id))
            self.assertEquals(execution['status'], 'terminated')

    def test_executions_list_with_params(self):
        params = {'deployment_id': self.first_deployment_id}
        response = self.client.executions.list(**params)
        self.assertEqual(1, len(response), 'expecting 1 executions result, '
                                           'got {0}'.format(len(response)))
        for execution in response:
            self.assertIn(execution['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertIn(execution['blueprint_id'],
                          (self.first_blueprint_id, self.sec_blueprint_id))
            self.assertEquals(execution['status'], 'terminated')

    def test_node_instances_list_no_params(self):
        response = self.client.node_instances.list()
        self.assertEqual(4, len(response), 'expecting 4 node instance results,'
                                           ' got {0}'.format(len(response)))
        for node_instance in response:
            self.assertIn(node_instance['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertEquals(node_instance['state'], 'uninitialized')

    def test_node_instances_list_with_params(self):
        params = {'deployment_id': self.first_deployment_id}
        response = self.client.node_instances.list(**params)
        self.assertEqual(2, len(response), 'expecting 2 node instance results,'
                                           ' got {0}'.format(len(response)))
        for instance in response:
            self.assertEquals(instance['deployment_id'],
                              self.first_deployment_id)

    # special parameter 'node_name' is converted to 'node_id' on the server
    def test_node_instances_list_with_node_name_filter(self):
        filter_params = {'node_name': 'http_web_server'}
        response = self.client.node_instances.list(**filter_params)
        self.assertEqual(2, len(response), 'expecting 1 node instance result,'
                                           ' got {0}'.format(len(response)))
        for node_instance in response:
            self.assertIn(node_instance['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertEquals(node_instance['state'], 'uninitialized')

        self._put_n_deployment_modifications(id_prefix='test',
                                             number_of_modifications=2,
                                             skip_creation=True)
        response = self.client.deployment_modifications.list()
        self.assertEqual(2, len(response), 'expecting 2 deployment mod '
                                           'results, got {0}'
                         .format(len(response)))
        for modification in response:
            self.assertIn(modification['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertIn(modification['status'], ('finished', 'started'))

    def test_deployment_modifications_list_with_params(self):
        params = {'deployment_id': self.first_deployment_id}
        self._put_n_deployment_modifications(id_prefix='test',
                                             number_of_modifications=2,
                                             skip_creation=True)
        response = self.client.deployment_modifications.list(**params)
        self.assertEqual(1, len(response), 'expecting 1 deployment mod '
                                           'results, got {0}'
                         .format(len(response)))
        for modification in response:
            self.assertEquals(modification['deployment_id'],
                              self.first_deployment_id)
            self.assertIn(modification['status'], ('finished', 'started'))

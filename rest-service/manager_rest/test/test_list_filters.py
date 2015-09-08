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

from nose.plugins.attrib import attr

from manager_rest.test import base_test
from manager_rest.test.base_list_test import BaseListTest
from manager_rest import models
from manager_rest import manager_exceptions
from cloudify_rest_client.exceptions import CloudifyClientError


@attr(client_min_version=2, client_max_version=base_test.LATEST_API_VERSION)
class ResourceListFiltersTestCase(BaseListTest):

    def setUp(self):
        super(ResourceListFiltersTestCase, self).setUp()
        (self.first_blueprint_id,
            self.first_deployment_id,
            self.sec_blueprint_id,
            self.sec_deployment_id) = self._put_two_test_deployments()

    def test_deployments_list_with_filters(self):
        filter_fields = {'id': self.first_deployment_id,
                         'blueprint_id': self.first_blueprint_id}
        response = self.get('/deployments', query_params=filter_fields).json

        self.assertEqual(len(response), 1, 'expecting 1 deployment result, '
                                           'got {0}'.format(len(response)))
        self.assertDictContainsSubset(filter_fields, response[0],
                                      'expecting filtered results having '
                                      'filters {0}, got {1}'
                                      .format(filter_fields, response[0]))

    def test_deployments_list_non_existent_filters(self):
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.deployments.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(models.Deployment.fields, e)

    def test_deployments_list_no_filters(self):
        response = self.get('/deployments', query_params=None).json
        self.assertEqual(2, len(response), 'expecting 2 deployment results, '
                                           'got {0}'.format(len(response)))

        expected_results = {'id': self.first_deployment_id,
                            'blueprint_id': self.first_blueprint_id,
                            'id': self.sec_deployment_id,
                            'blueprint_id': self.sec_blueprint_id}
        self.assertDictContainsSubset(expected_results, response[0],
                                      'expecting results having '
                                      'values {0}, got {1}'
                                      .format(expected_results, response[0]))

    def test_nodes_list_with_filters(self):
        filter_params = {'deployment_id': self.first_deployment_id}
        response = self.get('/nodes', query_params=filter_params).json
        self.assertEqual(2, len(response), 'expecting 2 node results, '
                                           'got {0}'.format(len(response)))
        for node in response:
            self.assertEquals(node['deployment_id'], self.first_deployment_id)
            self.assertEquals(node['blueprint_id'], self.first_blueprint_id)

    def test_nodes_list_no_filters(self):
        response = self.get('/nodes', query_params=None).json
        self.assertEqual(4, len(response), 'expecting 4 node results, '
                                           'got {0}'.format(len(response)))
        for node in response:
            self.assertIn(node['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertIn(node['blueprint_id'],
                          (self.first_blueprint_id, self.sec_blueprint_id))

    def test_nodes_list_non_existent_filters(self):
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.nodes.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(models.DeploymentNode.fields, e)

    def test_executions_list_with_filters(self):
        filter_params = {'deployment_id': self.first_deployment_id,
                         '_include_system_workflows': True}
        response = self.get('/executions', query_params=filter_params).json
        self.assertEqual(1, len(response), 'expecting 1 execution results, '
                                           'got {0}'.format(len(response)))
        execution = response[0]
        self.assertEqual(execution['deployment_id'], self.first_deployment_id)
        self.assertEquals(execution['status'], 'terminated')

    def test_executions_list_no_filters(self):
        response = self.get('/executions', query_params=None).json
        self.assertEqual(2, len(response), 'expecting 2 executions results, '
                                           'got {0}'.format(len(response)))
        for execution in response:
            self.assertIn(execution['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertIn(execution['blueprint_id'],
                          (self.first_blueprint_id, self.sec_blueprint_id))
            self.assertEquals(execution['status'], 'terminated')

    def assert_bad_parameter_error(self, fields, e):
        self.assertEqual(400, e.status_code)
        error = manager_exceptions.BadParametersError
        self.assertEquals(error.BAD_PARAMETERS_ERROR_CODE, e.error_code)
        for filter_val in fields:
            self.assertIn(filter_val,
                          e.message,
                          'expecting available filter names be contained '
                          'in error message {0}'.format(e.message))

    def test_executions_list_non_existent_filters(self):
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.executions.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(models.Execution.fields, e)

    def test_node_instances_list_no_filters(self):
        response = self.get('/node-instances', query_params=None).json
        self.assertEqual(4, len(response), 'expecting 4 node instance results,'
                                           ' got {0}'.format(len(response)))
        for node_instance in response:
            self.assertIn(node_instance['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertEquals(node_instance['state'], 'uninitialized')

    def test_node_instances_list_with_filters(self):
        filter_params = {'deployment_id': self.first_deployment_id}
        response = self.get('/node-instances', query_params=filter_params).json
        self.assertEqual(2, len(response), 'expecting 2 node instance results,'
                                           ' got {0}'.format(len(response)))
        for node_instance in response:
            self.assertEqual(node_instance['deployment_id'],
                             self.first_deployment_id)
            self.assertEquals(node_instance['state'], 'uninitialized')

    def test_node_instances_list_non_existent_filters(self):
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.node_instances.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(
                models.DeploymentNodeInstance.fields, e)

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

    def test_deployment_modifications_list_no_filters(self):
        self._put_two_deployment_modifications()
        response = self.get('/deployment-modifications',
                            query_params=None).json
        self.assertEqual(2, len(response), 'expecting 2 deployment mod '
                                           'results, got {0}'
                         .format(len(response)))
        for modification in response:
            self.assertIn(modification['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertIn(modification['status'], ('finished', 'started'))

    def test_deployment_modifications_list_with_filters(self):
        self._put_two_deployment_modifications()
        filter_params = {'deployment_id': self.first_deployment_id}
        response = self.get('/deployment-modifications',
                            query_params=filter_params).json
        self.assertEqual(1, len(response), 'expecting 1 deployment mod '
                                           'results, got {0}'
                         .format(len(response)))
        modification = response[0]
        self.assertDictContainsSubset(filter_params, modification,
                                      'expecting results having '
                                      'values {0}, got {1}'
                                      .format(filter_params, modification))
        self.assertEquals(modification['status'], 'finished')

    def test_deployment_modifications_list_non_existent_filters(self):
        self._put_two_deployment_modifications()
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.deployment_modifications.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(
                models.DeploymentModification.fields, e)

    def test_blueprints_list_with_filters(self):
        filter_params = {'id': self.first_blueprint_id}
        response = self.get('/blueprints', query_params=filter_params).json
        self.assertEqual(1, len(response), 'expecting 1 blueprint result,'
                                           ' got {0}'.format(len(response)))
        blueprint = response[0]
        self.assertDictContainsSubset(filter_params, blueprint,
                                      'expecting results having '
                                      'values {0}, got {1}'
                                      .format(filter_params, blueprint))
        self.assertEquals(self.first_blueprint_id, blueprint['id'])
        self.assertIsNotNone(response[0]['plan'])

    def test_blueprints_list_no_filters(self):
        response = self.get('/blueprints', query_params=None).json
        self.assertEqual(2, len(response), 'expecting 2 blueprint result,'
                                           ' got {0}'.format(len(response)))
        for blueprint in response:
            self.assertIn(blueprint['id'],
                          (self.first_blueprint_id, self.sec_blueprint_id))
            self.assertIsNotNone(blueprint['plan'])

    def test_blueprints_list_non_existent_filters(self):
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.blueprints.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(models.BlueprintState.fields, e)

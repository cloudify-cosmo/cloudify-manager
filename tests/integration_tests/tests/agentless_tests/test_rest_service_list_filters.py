########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests import utils as test_utils
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_rest

TEST_PACKAGE_NAME = 'cloudify-script-plugin'
TEST_PACKAGE_VERSION = '1.2'
OLD_TEST_PACKAGE_VERSION = '1.1'


@pytest.mark.usefixtures('mock_workflows_plugin')
@pytest.mark.usefixtures('testmockoperations_plugin')
class TestRestServiceListFilters(AgentlessTestCase):
    def setUp(self):
        super(TestRestServiceListFilters, self).setUp()
        self.first_deployment_id, \
            self.first_blueprint_id, \
            self.sec_deployment_id, \
            self.sec_blueprint_id = self._put_two_deployments()
        self.deployment_id_filter = {'deployment_id': self.first_deployment_id}
        self.blueprint_id_filter = {'blueprint_id': self.first_blueprint_id}

    def _put_two_deployments(self):
        dsl_path = resource("dsl/deployment_modification_operations.yaml")
        first_deployment, _ = self.deploy_application(dsl_path)
        sec_deployment, _ = self.deploy_application(dsl_path)
        return first_deployment.id, first_deployment.blueprint_id,\
            sec_deployment.id, sec_deployment.blueprint_id

    def test_nodes_list_with_filters(self):
        filter_params = {'blueprint_id': self.first_blueprint_id,
                         'deployment_id': self.first_deployment_id}
        response = self.client.nodes.list(**filter_params)
        self.assertEqual(len(response), 3, 'expecting 3 node results matching'
                                           ' deployment_id {0} and '
                                           'blueprint_id {1}'
                                           .format(self.first_deployment_id,
                                                   self.first_blueprint_id))
        for node in response:
            self.assertEqual(node.deployment_id, self.first_deployment_id)
            self.assertEqual(node.blueprint_id, self.first_blueprint_id)

    def test_nodes_list_with_filters_and_include(self):
        filter_params = {'blueprint_id': self.first_blueprint_id,
                         'deployment_id': self.first_deployment_id}
        include = ['id']

        response = self.client.nodes.list(_include=include, **filter_params)
        self.assertEqual(len(response), 3, 'expecting 3 node results matching'
                                           ' deployment_id {0} and '
                                           'blueprint_id {1}'
                         .format(self.first_deployment_id,
                                 self.first_blueprint_id))
        for node in response:
            self.assertIsNone(node.deployment_id, 'Expecting deployment_id to '
                                                  'be None')
            self.assertIsNotNone(node.id, 'Expecting id not to be None')

    def test_nodes_list_non_existent_filters(self):
        filter_params = {'blueprint_id': self.first_blueprint_id,
                         'deployment_id': self.sec_deployment_id}
        response = self.client.nodes.list(**filter_params)
        self.assertEqual(len(response), 0, 'expecting 0 node results matching'
                                           ' deployment_id {0} and '
                                           'blueprint_id {1}'
                         .format(self.first_deployment_id,
                                 self.first_blueprint_id))

    def test_nodes_list_no_filters(self):
        response = self.client.nodes.list()
        self.assertEqual(len(response), 6, 'expecting 6 node results matching'
                                           ' deployment_id {id}'
                         .format(id=self.first_deployment_id))
        for node in response:
            self.assertIn(node.deployment_id,
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertIn(node.blueprint_id,
                          (self.first_blueprint_id, self.sec_blueprint_id))

    def test_node_instances_list_with_filters(self):
        res = self.client.node_instances.list(**self.deployment_id_filter)
        self.assertEqual(len(res), 3, 'expecting 3 node instance results'
                                      ' matching deployment_id {0}'
                                      .format(self.first_deployment_id))
        for node_instance in res:
            self.assertEqual(node_instance.deployment_id,
                             self.first_deployment_id)

    def test_node_instances_list_with_filters_multiple_values(self):
        self.multiple_value_filters = \
            {'deployment_id': [self.first_deployment_id,
                               self.sec_deployment_id],
             'node_id': ['webserver',
                         'compute']}
        res = \
            self.client.node_instances.list(
                **self.multiple_value_filters)
        self.assertEqual(len(res), 4, 'expecting 4 node instance results'
                                      ' matching {0}'
                         .format(self.multiple_value_filters))
        for node_instance in res:
            for key in self.multiple_value_filters:
                self.assertIn(node_instance[key],
                              self.multiple_value_filters[key])

    def test_node_instances_list_no_filters(self):
        response = self.client.node_instances.list()
        self.assertEqual(len(response), 6, 'expecting 6 node instance results'
                                           ' matching deployment_id {0}'
                                           .format(self.first_deployment_id))
        for node_instance in response:
            self.assertIn(node_instance.deployment_id,
                          (self.first_deployment_id, self.sec_deployment_id))

    def test_deployments_list_with_filters(self):
        id_filter = {'id': self.first_deployment_id}
        response = self.client.deployments.list(**id_filter)
        self.assertEqual(len(response), 1, 'expecting 1 deployment results'
                                           ' matching deployment_id {0} {1}'
                         .format(self.first_deployment_id, len(response)))
        deployment = response[0]
        self.assertEqual(deployment['id'], self.first_deployment_id)

    def test_deployments_list_no_filters(self):
        response = self.client.deployments.list()
        self.assertEqual(len(response), 2, 'expecting 2 deployment results'
                                           ' matching deployment_id {0}'
                         .format(self.first_deployment_id))
        for deployment in response:
            self.assertIn(deployment['id'],
                          (self.first_deployment_id, self.sec_deployment_id))

    def test_executions_list_with_filters(self):
        res = self.client.executions.list(**self.deployment_id_filter)
        self.assertEqual(len(res), 2, 'expecting 2 execution results'
                                      ' matching deployment_id {0} {1}'
                         .format(self.first_deployment_id, len(res)))
        for execution in res:
            self.assertEqual(execution.deployment_id,
                             self.first_deployment_id)

    def test_executions_list_no_filters(self):
        response = self.client.executions.list()
        self.assertEqual(len(response), 6, 'expecting 6 execution results'
                                           ' matching deployment_id {0} {1}'
                         .format(self.first_deployment_id, len(response)))
        for execution in response:
            if execution.deployment_id:
                self.assertIn(
                    execution.deployment_id,
                    (self.first_deployment_id, self.sec_deployment_id))

    def test_blueprints_list_with_filters(self):
        id_filter = {'id': self.first_blueprint_id}
        res = self.client.blueprints.list(**id_filter)
        self.assertEqual(len(res), 1, 'expecting 1 blueprint result'
                                      ' matching blueprint_id {0} {1}'
                         .format(self.first_blueprint_id, len(res)))
        blueprint = res[0]
        self.assertEqual(blueprint.id, self.first_blueprint_id)

    def test_blueprints_list_no_filters(self):
        res = self.client.blueprints.list()
        self.assertEqual(len(res), 2, 'expecting 2 blueprint results '
                                      'matching blueprint_id {0} {1}'
                         .format(self.first_blueprint_id, len(res)))
        for blueprint in res:
            self.assertIn(blueprint.id,
                          (self.first_blueprint_id, self.sec_blueprint_id))

    def test_plugins_list_with_filters(self):
        test_utils.upload_mock_plugin(
            self.client,
            TEST_PACKAGE_NAME,
            TEST_PACKAGE_VERSION)
        sec_plugin_id = test_utils.upload_mock_plugin(
            self.client,
            TEST_PACKAGE_NAME,
            OLD_TEST_PACKAGE_VERSION)['id']
        filter_field = {'id': sec_plugin_id}
        response = self.client.plugins.list(**filter_field)

        self.assertEqual(len(response), 1, 'expecting 1 plugin result, '
                                           'got {0}'.format(len(response)))
        self._assertDictContainsSubset(filter_field, response[0])

    def test_plugins_list_no_filters(self):
        test_utils.upload_mock_plugin(
            self.client,
            TEST_PACKAGE_NAME,
            TEST_PACKAGE_VERSION)
        test_utils.upload_mock_plugin(
            self.client,
            TEST_PACKAGE_NAME,
            OLD_TEST_PACKAGE_VERSION)
        plugins = [(p.package_name, p.package_version)
                   for p in self.client.plugins.list()]

        assert (TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION) in plugins
        assert (TEST_PACKAGE_NAME, OLD_TEST_PACKAGE_VERSION) in plugins

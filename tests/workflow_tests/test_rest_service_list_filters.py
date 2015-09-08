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

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy


class TestRestServiceListFilters(TestCase):

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
        first_deployment, _ = deploy(dsl_path)
        sec_deployment, _ = deploy(dsl_path)
        return first_deployment.id, first_deployment.blueprint_id,\
            sec_deployment.id, sec_deployment.blueprint_id

    def test_nodes_list_with_filters(self):
        filter_params = {'blueprint_id': self.first_blueprint_id,
                         'deployment_id': self.first_deployment_id}
        response = self.client.nodes.list(**filter_params)
        self.assertEquals(len(response), 3, 'expecting 3 node results matching'
                                            ' deployment_id {0} and '
                                            'blueprint_id {1}'
                                            .format(self.first_deployment_id,
                                                    self.first_blueprint_id))
        for node in response:
            self.assertEquals(node.deployment_id, self.first_deployment_id)
            self.assertEquals(node.blueprint_id, self.first_blueprint_id)

    def test_nodes_list_with_filters_and_include(self):
        filter_params = {'blueprint_id': self.first_blueprint_id,
                         'deployment_id': self.first_deployment_id}
        include = ['id']

        response = self.client.nodes.list(_include=include, **filter_params)
        self.assertEquals(len(response), 3, 'expecting 3 node results matching'
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
        self.assertEquals(len(response), 0, 'expecting 0 node results matching'
                                            ' deployment_id {0} and '
                                            'blueprint_id {1}'
                          .format(self.first_deployment_id,
                                  self.first_blueprint_id))

    def test_nodes_list_no_filters(self):
        response = self.client.nodes.list()
        self.assertEquals(len(response), 6, 'expecting 6 node results matching'
                                            ' deployment_id {id}'
                          .format(id=self.first_deployment_id))
        for node in response:
            self.assertIn(node.deployment_id,
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertIn(node.blueprint_id,
                          (self.first_blueprint_id, self.sec_blueprint_id))

    def test_node_instances_list_with_filters(self):
        res = self.client.node_instances.list(**self.deployment_id_filter)
        self.assertEquals(len(res), 3, 'expecting 3 node instance results'
                                       ' matching deployment_id {0}'
                                       .format(self.first_deployment_id))
        for node_instance in res:
            self.assertEquals(node_instance.deployment_id,
                              self.first_deployment_id)

    def test_node_instances_list_no_filters(self):
        response = self.client.node_instances.list()
        self.assertEquals(len(response), 6, 'expecting 6 node instance results'
                                            ' matching deployment_id {0}'
                                            .format(self.first_deployment_id))
        for node_instance in response:
            self.assertIn(node_instance.deployment_id,
                          (self.first_deployment_id, self.sec_deployment_id))

    def test_deployments_list_with_filters(self):
        id_filter = {'id': self.first_deployment_id}
        response = self.client.deployments.list(**id_filter)
        self.assertEquals(len(response), 1, 'expecting 1 deployment results'
                                            ' matching deployment_id {0} {1}'
                          .format(self.first_deployment_id, len(response)))
        deployment = response[0]
        self.assertEquals(deployment['id'], self.first_deployment_id)

    def test_deployments_list_no_filters(self):
        response = self.client.deployments.list()
        self.assertEquals(len(response), 2, 'expecting 2 deployment results'
                                            ' matching deployment_id {0}'
                          .format(self.first_deployment_id))
        for deployment in response:
            self.assertIn(deployment['id'],
                          (self.first_deployment_id, self.sec_deployment_id))

    def test_executions_list_with_filters(self):
        res = self.client.executions.list(**self.deployment_id_filter)
        self.assertEquals(len(res), 2, 'expecting 2 execution results'
                                       ' matching deployment_id {0} {1}'
                          .format(self.first_deployment_id, len(res)))
        for execution in res:
            self.assertEquals(execution.deployment_id,
                              self.first_deployment_id)

    def test_executions_list_no_filters(self):
        response = self.client.executions.list()
        self.assertEquals(len(response), 4, 'expecting 4 execution results'
                                            ' matching deployment_id {0} {1}'
                          .format(self.first_deployment_id, len(response)))
        for execution in response:
            self.assertIn(execution.deployment_id,
                          (self.first_deployment_id, self.sec_deployment_id))

    def test_blueprints_list_with_filters(self):
        id_filter = {'id': self.first_blueprint_id}
        res = self.client.blueprints.list(**id_filter)
        self.assertEquals(len(res), 1, 'expecting 1 blueprint result'
                                       ' matching blueprint_id {0} {1}'
                          .format(self.first_blueprint_id, len(res)))
        blueprint = res[0]
        self.assertEquals(blueprint.id, self.first_blueprint_id)

    def test_blueprints_list_no_filters(self):
        res = self.client.blueprints.list()
        self.assertEquals(len(res), 2, 'expecting 2 blueprint results '
                                       'matching blueprint_id {0} {1}'
                          .format(self.first_blueprint_id, len(res)))
        for blueprint in res:
            self.assertIn(blueprint.id,
                          (self.first_blueprint_id, self.sec_blueprint_id))

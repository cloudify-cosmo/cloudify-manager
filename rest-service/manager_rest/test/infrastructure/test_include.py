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

from unittest import mock

from cloudify_rest_client.exceptions import NoSuchIncludeFieldError

from manager_rest.test import base_test
from manager_rest.test.utils import node_intance_counts
from manager_rest.storage import ListResult, models


class IncludeQueryParamTests(base_test.BaseServerTestCase):

    def setUp(self):
        super(IncludeQueryParamTests, self).setUp()
        bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )
        dep = models.Deployment(
            id='dep1',
            blueprint=bp,
            creator=self.user,
            tenant=self.tenant,
        )
        models.Execution(
            id='exc1',
            workflow_id='install',
            deployment=dep,
            creator=self.user,
            tenant=self.tenant,
        )
        node = models.Node(
            id='node1',
            type='node',
            deployment=dep,
            creator=self.user,
            tenant=self.tenant,
            **node_intance_counts(2)
        )
        for num in range(2):
            models.NodeInstance(
                id=f'{node.id}_{num}',
                node=node,
                state='started',
                creator=self.user,
                tenant=self.tenant,
            )
        self.deployment_id = dep.id

    def test_include_propagation_to_model(self):
        self._test_include_propagation_to_model(
            [models.Blueprint],
            dict(
                include=[u'id'],
                filters={'is_hidden': False},
                pagination={},
                sort={},
                all_tenants=False,
                substr_filters=None,
                get_all_results=False,
                filter_rules=None)
        )

    def _test_include_propagation_to_model(self,
                                           expected_blueprints_list_args,
                                           expected_blueprints_list_kwargs):
        # test that the "include" parameter does not only filter the response
        # fields at the end of the request, but also propagates to the Model
        # section, for more efficient storage queries
        with mock.patch('manager_rest.storage.storage_manager'
                        '.SQLStorageManager.list') as sm_list_bp:
            mock_meta = {'pagination': {'total': 0,
                                        'size': 0,
                                        'offset': 0}}
            sm_list_bp.return_value = ListResult([], mock_meta)
            self.client.blueprints.list(_include=['id'])
            sm_list_bp.assert_called_once_with(
                *expected_blueprints_list_args,
                **expected_blueprints_list_kwargs)

    def test_blueprints(self):
        response = self.client.blueprints.list(_include=['id'])
        for b in response:
            self.assertEqual(1, len(b))
            self.assertTrue('id' in b)
        self.assertRaises(
            NoSuchIncludeFieldError,
            lambda: self.client.blueprints.list(_include=['hello', 'world']))
        blueprint_id = self.client.blueprints.list()[0].id
        response = self.client.blueprints.get(blueprint_id,
                                              _include=['id', 'created_at'])
        self.assertEqual(2, len(response))
        self.assertEqual(blueprint_id, response.id)
        self.assertTrue(response.created_at)
        self.assertRaises(
            NoSuchIncludeFieldError,
            lambda: self.client.blueprints.get(blueprint_id,
                                               _include=['hello']))

    def test_deployments(self):
        response = self.client.deployments.list(_include=['id'])
        for d in response:
            self.assertEqual(1, len(d))
            self.assertTrue('id' in d)
            deployment_id = d.id
        self.assertRaises(
            NoSuchIncludeFieldError,
            lambda: self.client.deployments.list(_include=['hello']))

        response = self.client.deployments.get(deployment_id,
                                               _include=['id', 'blueprint_id'])
        self.assertEqual(2, len(response))
        self.assertEqual(deployment_id, response.id)
        self.assertIsNotNone(response.blueprint_id)
        self.assertRaises(
            NoSuchIncludeFieldError,
            lambda: self.client.deployments.get(deployment_id,
                                                _include=['hello']))

    def test_executions(self):
        deployment_id = self.client.deployments.list()[0].id
        response = self.client.executions.list(
            deployment_id=deployment_id,
            _include=['id']
        )
        for e in response:
            self.assertEqual(1, len(e))
            self.assertIn('id', e)
            execution_id = e.id
        self.assertRaises(
            NoSuchIncludeFieldError,
            lambda: self.client.executions.list(deployment_id=deployment_id,
                                                _include=['hello', 'world']))
        response = self.client.executions.get(execution_id,
                                              _include=['id', 'created_at'])
        self.assertEqual(2, len(response))
        self.assertEqual(execution_id, response.id)
        self.assertIsNotNone(response.created_at)

    def test_execution_with_status_display_field(self):
        # status_display is special because it's a hybrid_property
        deployment_id = self.client.deployments.list()[0].id
        response = self.client.executions.list(
            deployment_id=deployment_id,
            _include=['id', 'status_display']
        )
        for e in response:
            self.assertEqual(2, len(e))
            self.assertIn('id', e)
            self.assertIn('status_display', e)

    def test_nodes(self):
        deployment_id = self.client.deployments.list()[0].id
        response = self.client.nodes.list(deployment_id=deployment_id,
                                          _include=['id', 'properties'])
        for n in response:
            self.assertEqual(2, len(n))
            self.assertTrue('id' in n)
            self.assertTrue('properties' in n)
        self.assertRaises(
            NoSuchIncludeFieldError,
            lambda: self.client.nodes.list(_include=['hello']))

    def test_node_instances(self):
        response = self.client.node_instances.list(
            _include=['id', 'runtime_properties'])
        for n in response:
            self.assertEqual(2, len(n))
            self.assertTrue('id' in n)
            self.assertTrue('runtime_properties' in n)
            instance_id = n.id
        self.assertRaises(
            NoSuchIncludeFieldError,
            lambda: self.client.node_instances.list(_include=['hello']))
        response = self.client.node_instances.get(instance_id, _include=['id'])
        self.assertEqual(1, len(response))
        self.assertTrue(instance_id, response.id)
        self.assertRaises(
            NoSuchIncludeFieldError,
            lambda: self.client.node_instances.get(instance_id,
                                                   _include=['hello']))

    def test_provider_context(self):
        response = self.client.manager.get_context(_include=['name'])
        self.assertEqual(1, len(response))
        self.assertRaises(
            NoSuchIncludeFieldError,
            lambda: self.client.manager.get_context(_include=['hello']))

    def test_association_proxy_include(self):
        response = self.client.deployments.get(
            self.deployment_id, _include=['blueprint_id'])
        self.assertEqual(response, {'blueprint_id': 'bp1'})

    def test_created_by_include(self):
        response = self.client.deployments.get(
            self.deployment_id, _include=['created_by'])
        self.assertEqual(response, {'created_by': 'admin'})

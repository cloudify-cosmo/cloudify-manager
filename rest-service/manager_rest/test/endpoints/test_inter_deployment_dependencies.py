# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import uuid

from mock import patch

from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify.deployment_dependencies import create_deployment_dependency

from manager_rest.manager_exceptions import NotFoundError, ConflictError
from manager_rest.rest.rest_utils import RecursiveDeploymentDependencies

from manager_rest.test import base_test
from manager_rest.test.base_test import BaseServerTestCase


class InterDeploymentDependenciesTest(BaseServerTestCase):
    def setUp(self):
        super(InterDeploymentDependenciesTest, self).setUp()
        self.dependency_creator = 'dependency_creator'
        self.source_deployment = 'source_deployment'
        self.target_deployment = 'target_deployment'
        self.dependency = create_deployment_dependency(
            self.dependency_creator,
            self.source_deployment,
            self.target_deployment)
        self.put_mock_deployments(self.source_deployment,
                                  self.target_deployment)

    @patch('manager_rest.rest.rest_utils.RecursiveDeploymentDependencies'
           '.assert_no_cyclic_dependencies')
    def test_adds_dependency_and_retrieves_it(self, mock_assert_no_cycles):
        dependency = self.client.inter_deployment_dependencies.create(
            **self.dependency)
        mock_assert_no_cycles.assert_called()
        response = self.client.inter_deployment_dependencies.list()
        if response:
            self.assertDictEqual(dependency, response[0])
        else:
            raise NotFoundError(**self.dependency)

    def test_deletes_existing_dependency(self):
        self.client.inter_deployment_dependencies.create(
            **self.dependency)
        self.assertEqual(
            1,
            len(self.client.inter_deployment_dependencies.list())
        )
        self.client.inter_deployment_dependencies.delete(
            **self.dependency)
        self.assertEqual(
            0,
            len(self.client.inter_deployment_dependencies.list())
        )

    def test_fails_to_delete_non_existing_dependency(self):
        message = 'not found'
        with self.assertRaisesRegex(CloudifyClientError, message) as cm:
            self.client.inter_deployment_dependencies.delete(
                **self.dependency)
        assert cm.exception.status_code == 404

    def test_list_dependencies_returns_empty_list(self):
        self.assertEqual(
            0,
            len(self.client.inter_deployment_dependencies.list())
        )

    def test_list_dependencies_returns_correct_list(self):
        dependency = self.client.inter_deployment_dependencies.create(
            **self.dependency)
        dependency_list = list(
            self.client.inter_deployment_dependencies.list())
        self.assertListEqual([dependency], dependency_list)

    @patch('manager_rest.rest.rest_utils.RecursiveDeploymentDependencies'
           '.add_dependency_to_graph')
    def test_adds_dependency_with_a_bad_source_and_target_deployments(
            self, mock_add_to_graph):
        source_deployment = self.source_deployment + '_doesnt_exist'
        target_deployment = self.target_deployment + '_doesnt_exist'
        error_msg_regex = '404: Given {1} deployment with ID `{0}` does ' \
                          'not exist\\.'
        with self.assertRaisesRegex(
                CloudifyClientError,
                error_msg_regex.format(source_deployment, 'source')):
            self.client.inter_deployment_dependencies.create(
                self.dependency_creator,
                source_deployment,
                self.target_deployment)
        with self.assertRaisesRegex(
                CloudifyClientError,
                error_msg_regex.format(target_deployment, 'target')):
            self.client.inter_deployment_dependencies.create(
                self.dependency_creator,
                self.source_deployment,
                target_deployment)
        mock_add_to_graph.assert_not_called()

    def test_deployment_creation_creates_dependencies(self):
        static_target_deployment = 'shared1'
        resource_id = 'i{0}'.format(uuid.uuid4())
        self.client.secrets.create('shared2_key', 'secret')

        self.put_deployment(
            blueprint_file_name='blueprint_with_capabilities.yaml',
            blueprint_id='i{0}'.format(uuid.uuid4()),
            deployment_id=static_target_deployment)

        self.put_deployment(
            blueprint_file_name='blueprint_with_static_and_runtime'
                                '_get_capability.yaml',
            blueprint_id=resource_id,
            deployment_id=resource_id)

        dependencies = self.client.inter_deployment_dependencies.list()
        self.assertEqual(2, len(dependencies))
        target_deployment_func = self._get_target_deployment_func(dependencies)
        static_dependency = self._get_static_dependency(dependencies)

        self._assert_dependency_values(static_dependency,
                                       static_target_deployment,
                                       resource_id)
        self.assertEqual(target_deployment_func,
                         {'get_secret': 'shared2_key'})

    @staticmethod
    def _get_target_deployment_func(dependencies_list):
        for dependency in dependencies_list:
            if 'property_function' in dependency.dependency_creator:
                return dependency['target_deployment_func']

    @staticmethod
    def _get_static_dependency(dependencies_list):
        for dependency in dependencies_list:
            if 'property_static' in dependency.dependency_creator:
                return dependency

    def _assert_dependency_values(self, dependency, target_deployment_id,
                                  resource_id):
        self.assertEqual(dependency.source_deployment_id,
                         resource_id)
        self.assertEqual(dependency.target_deployment_id,
                         target_deployment_id)

    def test_create_dependencies_graph(self):
        self._populate_dependencies_table()
        dep_graph = RecursiveDeploymentDependencies(self.sm)
        dep_graph.create_dependencies_graph()
        self.assertEqual(dep_graph.graph['0'], {'1', '2', '4'})
        self.assertEqual(dep_graph.graph['1'], {'3'})
        self.assertEqual(dep_graph.graph['4'], {'5'})

    def test_add_dependency_to_graph(self):
        self._populate_dependencies_table()
        dep_graph = RecursiveDeploymentDependencies(self.sm)
        dep_graph.create_dependencies_graph()
        dep_graph.add_dependency_to_graph('new_dep', '0')
        self.assertIn('new_dep', dep_graph.graph['0'])

    def test_remove_dependency_from_graph(self):
        self._populate_dependencies_table()
        dep_graph = RecursiveDeploymentDependencies(self.sm)
        dep_graph.create_dependencies_graph()
        dep_graph.remove_dependency_from_graph('5', '4')
        self.assertNotIn('4', dep_graph.graph)

    def test_adding_cyclic_dependency_fails(self):
        self._populate_dependencies_table()
        # 1,2,4 all depend on 1; 3 depends on 1 and 2; 5 depends on 4
        dep_graph = RecursiveDeploymentDependencies(self.sm)
        dep_graph.create_dependencies_graph()
        # 3 depends on 0. NOT a cycle
        dep_graph.assert_no_cyclic_dependencies('3', '0')
        # 0 depends on 3. Cycle! 0 -> 1 or 2 -> 3 -> 0
        with self.assertRaisesRegex(ConflictError, 'cyclic inter-deployment'):
            dep_graph.assert_no_cyclic_dependencies('0', '3')
        # 4 depends on 5. Cycle! 4 -> 5 -> 4
        with self.assertRaisesRegex(ConflictError, 'cyclic inter-deployment'):
            dep_graph.assert_no_cyclic_dependencies('4', '5')

    def test_retrieve_dependent_deployments(self):
        self._populate_dependencies_table()
        # 1,2,4 all depend on 1; 3 depends on 1 and 2; 5 depends on 4
        dep_graph = RecursiveDeploymentDependencies(self.sm)
        dep_graph.create_dependencies_graph()

        # for deployment '0':
        dependencies = dep_graph.retrieve_dependent_deployments('0')
        self.assertEqual(len(dependencies), 6)
        self.assertEqual(set([x['deployment'] for x in dependencies]),
                         {'1', '2', '3', '4', '5'})
        self.assertEqual(set([x['dependency_type'] for x in dependencies]),
                         {'deployment', 'component', 'sharedresource'})

        # for deployment '4':
        dependencies = dep_graph.retrieve_dependent_deployments('4')
        self.assertEqual(len(dependencies), 1)
        self.assertEqual(dependencies[0]['deployment'], '5')
        self.assertEqual(dependencies[0]['dependency_type'], 'deployment')
        self.assertEqual(dependencies[0]['dependent_node'], 'ip')

    def test_retrieve_dependencies_app_with_components(self):
        # create an IDD system with the following:
        # a central app `multi` depending on component `comp-top` and on
        # shared resource `resource`.
        # `comp-top` depends on `comp-bottom` which is shared with `sharing-1`
        # `sharing-2` depends on `resource`, `sharing-3` depends on `sharing-1`
        # and `capable` depends on `multi`.
        self.put_mock_deployments('capable', 'multi')
        self.put_mock_deployments('comp-top', 'comp-bottom')
        self.put_mock_deployments('sharing-2', 'resource')
        self.put_mock_deployments('sharing-3', 'sharing-1')
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('component.teiredcomponent',
                                           'multi', 'comp-top'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('sharedresource.vm',
                                           'multi', 'resource'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('sharedresource.vm',
                                           'sharing-2', 'resource'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('component.infra',
                                           'comp-top', 'comp-bottom'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('sharedresource.node1',
                                           'sharing-1', 'comp-bottom'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('sharedresource.mynode',
                                           'sharing-3', 'sharing-1'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('capability.ip',
                                           'capable', 'multi'))
        # if we try to uninstall/update/stop/delete `multi`,
        # we should be alerted of both its and its components' dependencies
        dep_graph = RecursiveDeploymentDependencies(self.sm)
        dep_graph.create_dependencies_graph()
        dependencies = dep_graph.retrieve_dependent_deployments('multi')
        self.assertEqual(len(dependencies), 3)
        self.assertEqual(set(x['deployment'] for x in dependencies),
                         {'capable', 'sharing-1', 'sharing-3'})

    def test_alerts_uninstall_deployment(self):
        self._prepare_dependent_deployments()
        self.assertRaisesRegex(
            CloudifyClientError,
            '1] Deployment `app` uses a shared resource from the current '
            'deployment in its node `vm`',
            self.client.executions.start,
            'infra',
            'uninstall'
        )

    def test_alerts_update_deployment(self):
        self._prepare_dependent_deployments()
        self.assertRaisesRegex(
            CloudifyClientError,
            '1] Deployment `app` uses a shared resource from the current '
            'deployment in its node `vm`',
            self.client.deployment_updates.update_with_existing_blueprint,
            'infra',
            inputs={'http_web_server_port': 8080}
        )

    def test_alerts_update_deployment_preview(self):
        self._prepare_dependent_deployments()
        update_result = \
            self.client.deployment_updates.update_with_existing_blueprint(
                'infra', inputs={'http_web_server_port': 8080}, preview=True)
        deployment_dependencies = update_result['recursive_dependencies']
        self.assertEqual(len(deployment_dependencies), 1)
        self.assertEqual(deployment_dependencies[0],
                         {'dependency_type': 'sharedresource',
                          'dependent_node': 'vm',
                          'tenant': 'default_tenant',
                          'deployment': 'app'})

    def test_alerts_delete_deployment(self):
        self._prepare_dependent_deployments()
        self.assertRaisesRegex(
            CloudifyClientError,
            '1] Deployment `app` uses a shared resource from the current '
            'deployment in its node `vm`',
            self.client.deployments.delete,
            'infra'
        )

    def test_alerts_force_uninstall_deployment_no_error(self):
        self._prepare_dependent_deployments()
        self.client.executions.start('infra', 'uninstall', force=True)

    def _prepare_dependent_deployments(self):
        self.put_deployment(
            blueprint_file_name='blueprint_with_inputs.yaml',
            blueprint_id='i{0}'.format(uuid.uuid4()),
            deployment_id='infra',
            inputs={'http_web_server_port': 80}
        )
        self.put_deployment(
            blueprint_file_name='blueprint.yaml',
            blueprint_id='i{0}'.format(uuid.uuid4()),
            deployment_id='app')
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('sharedresource.vm',
                                           'app',
                                           'infra'))

    def _populate_dependencies_table(self):
        self.put_mock_deployments('0', '1')
        self.put_mock_deployments('2', '3')
        self.put_mock_deployments('4', '5')
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('sample.vm', '1', '0'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('capability.host', '2', '0'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('component.infra', '3', '2'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('sharedresource.infra', '3', '1'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('sharedresource.mynode', '4', '0'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('capability.ip', '5', '4'))

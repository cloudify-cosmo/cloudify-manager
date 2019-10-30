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

from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest import utils
from manager_rest.storage import models

from manager_rest.test import base_test
from manager_rest.test.attribute import attr
from manager_rest.test.base_test import BaseServerTestCase


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class InterDeploymentDependenciesTest(BaseServerTestCase):
    def _put_mock_blueprint(self):
        blueprint_id = str(uuid.uuid4())
        now = utils.get_formatted_timestamp()
        return self.sm.put(
            models.Blueprint(
                id=blueprint_id,
                created_at=now,
                updated_at=now,
                main_file_name='abcd',
                plan={})
        )

    @staticmethod
    def _get_mock_deployment(deployment_id, blueprint):
        now = utils.get_formatted_timestamp()
        deployment = models.Deployment(
            id=deployment_id,
            created_at=now,
            updated_at=now,
        )
        deployment.blueprint = blueprint
        return deployment

    def _put_mock_deployments(self, source_deployment, target_deployment):
        blueprint = self._put_mock_blueprint()
        source_deployment = self._get_mock_deployment(source_deployment,
                                                      blueprint)
        self.sm.put(source_deployment)
        target_deployment = self._get_mock_deployment(target_deployment,
                                                      blueprint)
        self.sm.put(target_deployment)

    def setUp(self):
        super(InterDeploymentDependenciesTest, self).setUp()
        self.dependency_creator = str(uuid.uuid4())
        self.source_deployment = str(uuid.uuid4())
        self.target_deployment = str(uuid.uuid4())
        self.dependency_tuple = (self.dependency_creator,
                                 self.source_deployment,
                                 self.target_deployment)
        self._put_mock_deployments(self.source_deployment,
                                   self.target_deployment)

    def test_adds_dependency_and_retrieves_it(self):
        dependency = self.client.inter_deployment_dependencies.create(
            *self.dependency_tuple)
        response = self.client.inter_deployment_dependencies.get(
            *self.dependency_tuple)
        self.assertDictEqual(dependency, response)

    def test_fails_to_add_duplicate_dependency(self):
        self.client.inter_deployment_dependencies.create(
            *self.dependency_tuple)
        error_msg_regex = '.*Instance with ID .* cannot be added on .* or ' \
                          'with global visibility.*'
        with self.assertRaisesRegexp(CloudifyClientError, error_msg_regex):
            self.client.inter_deployment_dependencies.create(
                *self.dependency_tuple)

    def test_deletes_existing_dependency(self):
        self.client.inter_deployment_dependencies.create(
            *self.dependency_tuple)
        self.assertEqual(
            1,
            len(self.client.inter_deployment_dependencies.list())
        )
        self.client.inter_deployment_dependencies.delete(
            *self.dependency_tuple)
        self.assertEqual(
            0,
            len(self.client.inter_deployment_dependencies.list())
        )

    def test_fails_to_delete_non_existing_dependency(self):
        error_msg_regex = '.*404: Requested `InterDeploymentDependencies` ' \
                          'with ID `None` was not found \\(filters:.*'
        with self.assertRaisesRegexp(CloudifyClientError, error_msg_regex):
            self.client.inter_deployment_dependencies.delete(
                *self.dependency_tuple)

    def test_doesnt_fail_deleting_non_existing_dependency_with_flag(self):
        self.client.inter_deployment_dependencies.delete(
            *self.dependency_tuple, doesnt_exist_ok=True)

    def test_fails_to_get_non_existing_dependency(self):
        error_msg_regex = '.*404: Requested Inter-deployment Dependency ' \
                          'with params `dependency_creator: {0}, ' \
                          'source_deployment: {1}, target_deployment: {2}` ' \
                          'was not found.*'.format(*self.dependency_tuple)
        with self.assertRaisesRegexp(CloudifyClientError, error_msg_regex):
            self.client.inter_deployment_dependencies.get(
                *self.dependency_tuple)

    def test_list_dependencies_returns_empty_list(self):
        self.assertEqual(
            0,
            len(self.client.inter_deployment_dependencies.list())
        )

    def test_list_dependencies_returns_correct_list(self):
        dependency = self.client.inter_deployment_dependencies.create(
            *self.dependency_tuple)
        dependency_list = list(
            self.client.inter_deployment_dependencies.list())
        self.assertListEqual([dependency], dependency_list)

    def test_adds_dependency_with_a_bad_source_and_target_deployments(self):
        source_deployment = self.source_deployment + '_doesnt_exist'
        target_deployment = self.target_deployment + '_doesnt_exist'
        error_msg_regex = '.*404: Given {1} deployment with ID `{0}` does ' \
                          'not exist\\.'
        with self.assertRaisesRegexp(
                CloudifyClientError,
                error_msg_regex.format(source_deployment, 'source')):
            self.client.inter_deployment_dependencies.create(
                self.dependency_creator,
                source_deployment,
                self.target_deployment)
        with self.assertRaisesRegexp(
                CloudifyClientError,
                error_msg_regex.format(target_deployment, 'target')):
            self.client.inter_deployment_dependencies.create(
                self.dependency_creator,
                self.source_deployment,
                target_deployment)

    def test_deployment_creation_creates_dependencies(self):
        def get_static_and_runtime_dependencies(_dependencies):
            _static_dependency = None
            _runtime_dependency = None
            for _dependency in _dependencies:
                if 'property_static' in _dependency.dependency_creator:
                    _static_dependency = _dependency
                elif 'property_runtime' in _dependency.dependency_creator:
                    _runtime_dependency = _dependency
                else:
                    self.fail('Unexpected dependency creator "{0}".'
                              ''.format(_dependency.dependency_creator))
            return _static_dependency, _runtime_dependency

        def assert_dependency_values(dependency, target_deployment_id):
            self.assertEqual(dependency.source_deployment_id,
                             resource_id)
            self.assertEqual(dependency.target_deployment_id,
                             target_deployment_id)
        static_target_deployment = 'shared1'
        runtime_target_deployment = 'shared2'
        self.put_deployment(
            blueprint_file_name='blueprint_with_capabilities.yaml',
            blueprint_id='i{0}'.format(uuid.uuid4()),
            deployment_id=static_target_deployment)
        self.put_deployment(
            blueprint_file_name='blueprint_with_capabilities.yaml',
            blueprint_id='i{0}'.format(uuid.uuid4()),
            deployment_id=runtime_target_deployment)
        self.client.secrets.create('shared2_key', runtime_target_deployment)
        resource_id = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='blueprint_with_static_and_runtime'
                                '_get_capability.yaml',
            blueprint_id=resource_id,
            deployment_id=resource_id)

        dependencies = self.client.inter_deployment_dependencies.list()
        self.assertEqual(2, len(dependencies))
        static_dependency, runtime_dependency = \
            get_static_and_runtime_dependencies(dependencies)
        assert_dependency_values(static_dependency, static_target_deployment)
        assert_dependency_values(runtime_dependency, None)

        self.client.nodes.get(resource_id,
                              'compute_node',
                              evaluate_functions=True)
        dependencies = self.client.inter_deployment_dependencies.list()
        self.assertEqual(2, len(dependencies))
        static_dependency, runtime_dependency = \
            get_static_and_runtime_dependencies(dependencies)
        assert_dependency_values(static_dependency, static_target_deployment)
        assert_dependency_values(runtime_dependency, runtime_target_deployment)

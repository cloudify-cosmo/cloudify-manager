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

import mock
from collections import namedtuple

from cloudify.constants import COMPONENT
from cloudify.exceptions import NonRecoverableError
from cloudify.deployment_dependencies import dependency_creator_generator

from ..operations import create, delete
from cloudify_types.component.component import Component, CloudifyClientError
from .base_test_suite import (ComponentTestBase,
                              REST_CLIENT_EXCEPTION,
                              MOCK_TIMEOUT)


class TestDeploymentBase(ComponentTestBase):

    def setUp(self):
        super(TestDeploymentBase, self).setUp()
        self.sleep_mock = mock.patch('time.sleep', mock.MagicMock())
        self.sleep_mock.start()
        self._ctx.instance.runtime_properties['deployment'] = {}

    def tearDown(self):
        self.sleep_mock.stop()
        super(TestDeploymentBase, self).tearDown()


class TestDeployment(TestDeploymentBase):
    def test_delete_deployment_delete_deployment_failed(self):
        deployment_name = 'dep_name'
        self._ctx.instance.runtime_properties['deployment']['id'] =\
            deployment_name

        deployment_id_exists = 'cloudify_types.component.component' \
                               '.deployment_id_exists'
        with mock.patch(deployment_id_exists) as exists:
            exists.return_value = True

            self.cfy_mock_client.deployments.delete = REST_CLIENT_EXCEPTION
            error = self.assertRaises(NonRecoverableError,
                                      delete,
                                      deployment_id=deployment_name,
                                      timeout=MOCK_TIMEOUT)
            self.assertIn('action "delete" failed',
                          str(error))

    @mock.patch('cloudify_types.component.component.deployment_id_exists',
                return_value=False)
    @mock.patch('cloudify_types.component.polling.poll_with_timeout',
                return_value=True)
    def test_delete_deployment_delete_not_existing_deployment(self, *_):
        deployment_name = 'dep_name'
        self._ctx.instance.runtime_properties['deployment']['id'] =\
            deployment_name
        output = delete(
            operation='delete_deployment',
            deployment_id='dep_name',
            timeout=MOCK_TIMEOUT)
        self.assertTrue(output)

    @mock.patch('cloudify_types.component.polling.poll_with_timeout',
                return_value=True)
    def test_delete_deployment_success(self, _):
        self._ctx.instance.runtime_properties['deployment']['id'] = 'dep_name'
        self.cfy_mock_client.secrets.delete = mock.Mock()

        output = delete(
            operation='delete_deployment',
            deployment_id='dep_name',
            timeout=MOCK_TIMEOUT)
        self.assertTrue(output)

        self.cfy_mock_client.secrets.delete.assert_not_called()
        self.cfy_mock_client.plugins.delete.assert_not_called()
        self.assertEqual({}, self._ctx.instance.runtime_properties)

    def test_delete_deployment_any_dep_by_id(self):
        self._ctx.instance.runtime_properties['deployment']['id'] = 'dep_name'
        output = delete(
            operation='delete_deployment',
            deployment_id='test_deployments_delete',
            timeout=MOCK_TIMEOUT)
        self.assertTrue(output)

    def test_create_deployment_rest_client_error(self):
        self._ctx.instance.runtime_properties['deployment']['id'] = 'dep_name'

        self.cfy_mock_client.deployments.create = REST_CLIENT_EXCEPTION
        error = self.assertRaises(NonRecoverableError,
                                  create,
                                  deployment_id='test_deployments_create',
                                  blueprint_id='test_deployments_create',
                                  timeout=MOCK_TIMEOUT)
        self.assertIn('action "create" failed',
                      str(error))

    @mock.patch('cloudify_types.component.polling.poll_with_timeout',
                return_value=False)
    def test_create_deployment_timeout(self, _):
        self._ctx.instance.runtime_properties['deployment']['id'] = 'dep_name'
        self.cfy_mock_client.executions.set_existing_objects(
            [{
                'id': 'exec_id',
                'workflow_id': 'create_deployment_environment',
                'deployment_id': 'dep'
            }])

        self.assertRaisesRegex(
            NonRecoverableError,
            r'.*Execution timed out.*',
            create,
            deployment_id='test_create_deployment_timeout',
            blueprint_id='test',
            timeout=MOCK_TIMEOUT)

    @mock.patch('cloudify_types.component.polling.poll_with_timeout',
                return_value=True)
    def test_create_deployment_success(self, _):
        self.cfy_mock_client.executions.set_existing_objects(
            [{
                'id': 'exec_id',
                'workflow_id': 'create_deployment_environment',
                'deployment_id': 'dep'
            }])

        deployment = {'id': 'target_dep'}
        output = create(operation='create_deployment',
                        resource_config={'deployment': deployment},
                        timeout=MOCK_TIMEOUT)
        self.assertTrue(output)
        self.cfy_mock_client.inter_deployment_dependencies.create \
            .assert_called_with(
                dependency_creator=dependency_creator_generator(
                    COMPONENT, self._ctx.instance.id),
                source_deployment=self._ctx.deployment.id,
                target_deployment='target_dep'
            )

    @mock.patch('cloudify_types.component.polling.poll_with_timeout',
                return_value=True)
    def test_create_deployment_failed(self, _):
        self.cfy_mock_client.executions.set_existing_objects(
            [{
                'id': 'exec_id',
                'workflow_id': 'test',
                'deployment_id': 'dep'
            }])
        self.assertRaisesRegex(
            NonRecoverableError,
            r'.*No execution Found for component "node_id-test" deployment.*',
            create,
            operation='create_deployment',
            timeout=MOCK_TIMEOUT)

    def test_create_deployment_exists(self):
        self.cfy_mock_client.deployments.set_existing_objects([
            {'id': 'dep'}])
        self.assertRaises(NonRecoverableError,
                          create,
                          operation='create_deployment',
                          timeout=MOCK_TIMEOUT)


class TestComponentPlugins(TestDeploymentBase):

    @mock.patch('cloudify_types.component.component.os')
    @mock.patch('cloudify_types.component.component.zip_files',
                return_value="_zip")
    @mock.patch('cloudify_types.component.component.get_local_path',
                return_value='some_path')
    @mock.patch('cloudify_types.component.component.should_upload_plugin',
                return_value=True)
    def test_upload_plugins(self,
                            _,
                            mock_get_local_path,
                            mock_zip_files,
                            mock_os):
        plugin = mock.Mock()
        plugin.id = "CustomPlugin"
        self.cfy_mock_client.plugins.upload = mock.Mock(
            return_value=plugin)

        component = Component({'plugins': {
            'base_plugin': {
                'wagon_path': '_wagon_path',
                'plugin_yaml_path': '_plugin_yaml_path'}}})
        component._upload_plugins()
        mock_zip_files.assert_called_with(["some_path",
                                           "some_path"])
        mock_get_local_path.assert_has_calls([
            mock.call('_wagon_path', create_temp=True),
            mock.call('_plugin_yaml_path', create_temp=True)])
        mock_os.remove.assert_has_calls([
            mock.call('some_path'),
            mock.call('some_path'),
            mock.call('_zip')])

    @mock.patch('cloudify_types.component.component.zip_files',
                return_value="_zip")
    @mock.patch('cloudify_types.component.component.get_local_path',
                return_value='some_path')
    def test_upload_empty_plugins(self, mock_get_local_path, mock_zip_files):
        # empty plugins
        component = Component({'plugins': {}})
        component._upload_plugins()
        mock_zip_files.assert_not_called()
        mock_get_local_path.assert_not_called()

    @mock.patch('cloudify_types.component.polling.poll_with_timeout',
                return_value=True)
    def test_delete_deployment_success_with_plugins(self, _):
        self._ctx.instance.runtime_properties['deployment']['id'] = 'dep_name'
        self._ctx.instance.runtime_properties['plugins'] = {'plugin_id'}
        output = delete(
            operation='delete_deployment',
            deployment_id='dep_name',
            timeout=MOCK_TIMEOUT)
        self.assertTrue(output)

        self.cfy_mock_client.plugins.delete.assert_called_with(
            plugin_id='plugin_id')

    @mock.patch('cloudify_types.component.polling.poll_with_timeout',
                return_value=True)
    def test_delete_deployment_success_with_used_by_others_plugins(self, _):
        self._ctx.instance.runtime_properties['deployment']['id'] = 'dep_name'
        self._ctx.instance.runtime_properties['plugins'] = {'plugin_id'}

        self.cfy_mock_client.plugins.delete = mock.MagicMock(
            side_effect=CloudifyClientError(
                'Plugin "plugin_id" is currently in use in blueprints: '
                '... You can "force" plugin removal if needed'))

        output = delete(
            operation='delete_deployment',
            deployment_id='dep_name',
            timeout=MOCK_TIMEOUT)
        self.assertTrue(output)

        self.cfy_mock_client.plugins.delete.assert_called_with(
            plugin_id='plugin_id')

    def test_delete_deployment_failure_with_failed_removal_of_plugins(self):
        self._ctx.instance.runtime_properties['deployment']['id'] = 'dep_name'
        self._ctx.instance.runtime_properties['plugins'] = {'plugin_id'}

        self.cfy_mock_client.plugins.delete = mock.MagicMock(
            side_effect=CloudifyClientError('Failed plugin uninstall'))

        self.assertRaisesRegex(
            NonRecoverableError,
            r'.*Failed to remove plugin "plugin_id".*',
            delete,
            operation='delete_deployment',
            deployment_id='dep_name',
            timeout=MOCK_TIMEOUT)

        self.cfy_mock_client.plugins.delete.assert_called_with(
            plugin_id='plugin_id')


class TestComponentSecrets(TestDeploymentBase):
    Secret = namedtuple('Secret', ['value', 'key'])

    @mock.patch('cloudify_types.component.polling.poll_with_timeout',
                return_value=True)
    def test_create_deployment_success_with_secrets(self, _):
        self._ctx.node.properties['secrets'] = {'a': 'b'}
        self.cfy_mock_client.executions.set_existing_objects(
            [{
                'id': 'exec_id',
                'workflow_id': 'create_deployment_environment',
                'deployment_id': 'dep'
            }])

        self.cfy_mock_client.secrets.create = mock.Mock()

        output = create(operation='create_deployment',
                        timeout=MOCK_TIMEOUT)
        self.assertTrue(output)

        self.cfy_mock_client.secrets.create.assert_called_with(key='a',
                                                               value='b')

    def test_create_deployment_with_existing_secrets(self):
        self._ctx.node.properties['secrets'] = {'a': 'b'}
        self.cfy_mock_client.executions.set_existing_objects(
            [{
                'id': 'exec_id',
                'workflow_id': 'create_deployment_environment',
                'deployment_id': 'dep'
            }])

        self.cfy_mock_client.secrets.create = mock.Mock()
        self.cfy_mock_client.secrets.set_existing_objects([
            self.Secret(key='a', value='b')
        ])

        self.assertRaisesRegex(
            NonRecoverableError,
            r'.*The secrets: "a" already exist, not updating.*',
            create,
            operation='create_deployment',
            timeout=MOCK_TIMEOUT)

        self.cfy_mock_client.secrets.create.assert_not_called()

    @mock.patch('cloudify_types.component.polling.poll_with_timeout',
                return_value=True)
    def test_delete_deployment_success_with_secrets(self, _):
        self._ctx.instance.runtime_properties['deployment']['id'] = 'dep_name'
        self._ctx.instance.runtime_properties['secrets'] = {'a': 'b'}

        self.cfy_mock_client.secrets.delete = mock.Mock()

        output = delete(
            operation='delete_deployment',
            deployment_id='dep_name',
            timeout=MOCK_TIMEOUT)
        self.assertTrue(output)

        self.cfy_mock_client.secrets.delete.assert_called_with(key='a')

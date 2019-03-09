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

from cloudify.state import current_ctx
from cloudify.exceptions import NonRecoverableError

from .client_mock import MockCloudifyRestClient
from ..operations import create, delete
from cloudify_types.component.component import Component
from .base_test_suite import (ComponentTestBase,
                              REST_CLIENT_EXCEPTION,
                              MOCK_TIMEOUT)


class TestDeployment(ComponentTestBase):

    def setUp(self):
        super(TestDeployment, self).setUp()

        mock_sleep = mock.MagicMock()
        self.sleep_mock = mock.patch('time.sleep', mock_sleep)
        self.sleep_mock.start()

        self.total_patch = \
            mock.patch('cloudify_rest_client.responses.Pagination.total',
                       new_callable=mock.PropertyMock)
        self.total_patch = self.total_patch.start()
        self.total_patch.return_value = 1

        self.offset_patch = \
            mock.patch('cloudify_rest_client.responses.Pagination.offset',
                       new_callable=mock.PropertyMock)
        self.offset_patch = self.offset_patch.start()
        self.offset_patch.return_value = 1

    def tearDown(self):
        self.sleep_mock.stop()
        self.offset_patch.stop()
        self.total_patch.stop()
        super(TestDeployment, self).tearDown()

    def test_delete_deployment_rest_client_error(self):
        deployment_name = 'dep_name'
        self._ctx.instance.runtime_properties['deployment'] = {}
        self._ctx.instance.runtime_properties['deployment']['id'] =\
            deployment_name
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            cfy_mock_client.deployments.delete = REST_CLIENT_EXCEPTION
            mock_client.return_value = cfy_mock_client
            error = self.assertRaises(NonRecoverableError,
                                      delete,
                                      deployment_id=deployment_name,
                                      timeout=MOCK_TIMEOUT)
            self.assertIn('action "delete" failed',
                          error.message)

    def test_upload_plugins(self):
        get_local_path = mock.Mock(return_value="some_path")

        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            plugin = mock.Mock()
            plugin.id = "CustomPlugin"

            cfy_mock_client = MockCloudifyRestClient()
            cfy_mock_client.plugins.upload = mock.Mock(return_value=plugin)
            mock_client.return_value = cfy_mock_client
            with mock.patch(
                'cloudify_types.component.component.get_local_path',
                get_local_path
            ):
                zip_files = mock.Mock(return_value="_zip")
                with mock.patch(
                    'cloudify_types.component.component.zip_files',
                    zip_files
                ):
                    # dist of plugins
                    component = Component({'plugins': {
                        'base_plugin': {
                            'wagon_path': '_wagon_path',
                            'plugin_yaml_path': '_plugin_yaml_path'}}})
                    os_mock = mock.Mock()
                    with mock.patch('cloudify_types.component.component.os',
                                    os_mock):
                        component._upload_plugins()
                    zip_files.assert_called_with(["some_path", "some_path"])
                    get_local_path.assert_has_calls([
                        mock.call('_wagon_path', create_temp=True),
                        mock.call('_plugin_yaml_path', create_temp=True)])
                    os_mock.remove.assert_has_calls([
                        mock.call('some_path'),
                        mock.call('some_path'),
                        mock.call('_zip')])

    def test_upload_empty_plugins(self):
        get_local_path = mock.Mock(return_value="some_path")

        with mock.patch('cloudify.manager.get_rest_client'):
            zip_files = mock.Mock(return_value="_zip")
            with mock.patch(
                'cloudify_types.component.component.zip_files',
                zip_files
            ):
                # empty plugins
                component = Component({'plugins': {}})
                component._upload_plugins()
                zip_files.assert_not_called()
                get_local_path.assert_not_called()

    def test_upload_plugins_with_wrong_format(self):
        with mock.patch('cloudify.manager.get_rest_client'):
            component = Component({'plugins': True})
            error = self.assertRaises(NonRecoverableError,
                                      component._upload_plugins)
            self.assertIn('Wrong type in plugins: True',
                          error.message)

            component = Component({'plugins': {
                'base_plugin': {
                    'wagon_path': '',
                    'plugin_yaml_path': ''}}})
            error = self.assertRaises(NonRecoverableError,
                                      component._upload_plugins)
            self.assertIn("You should provide both values wagon_path: '' "
                          "and plugin_yaml_path: ''", error.message)

    def test_delete_deployment_success(self):
        self._ctx.instance.runtime_properties['deployment'] = {}
        self._ctx.instance.runtime_properties['deployment']['id'] = 'dep_name'
        self._ctx.instance.runtime_properties['secrets'] = {'a': 'b'}
        self._ctx.instance.runtime_properties['plugins'] = ['plugin_id']

        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            cfy_mock_client.secrets.delete = mock.Mock()
            cfy_mock_client.plugins.delete = mock.Mock()
            mock_client.return_value = cfy_mock_client

            poll_with_timeout_test = \
                'cloudify_types.component.polling.poll_with_timeout'
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = True
                output = delete(
                    operation='delete_deployment',
                    deployment_id='dep_name',
                    timeout=MOCK_TIMEOUT)
                self.assertTrue(output)

            cfy_mock_client.secrets.delete.assert_called_with(key='a')
            cfy_mock_client.plugins.delete.assert_called_with(
                plugin_id='plugin_id')

    def test_delete_deployment_any_dep_by_id(self):
        self._ctx.instance.runtime_properties['deployment'] = {}
        self._ctx.instance.runtime_properties['deployment']['id'] = 'dep_name'
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            mock_client.return_value = MockCloudifyRestClient()
            output = delete(
                operation='delete_deployment',
                deployment_id='test_deployments_delete',
                timeout=MOCK_TIMEOUT)
            self.assertTrue(output)

    def test_create_deployment_rest_client_error(self):
        self._ctx.instance.runtime_properties['deployment'] = {}
        self._ctx.instance.runtime_properties['deployment']['id'] = 'dep_name'
        self._ctx.instance.runtime_properties['deployment']['outputs'] = {}

        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            cfy_mock_client.deployments.create = REST_CLIENT_EXCEPTION
            mock_client.return_value = cfy_mock_client
            error = self.assertRaises(NonRecoverableError,
                                      create,
                                      deployment_id='test_deployments_create',
                                      blueprint_id='test_deployments_create',
                                      timeout=MOCK_TIMEOUT)
            self.assertIn('action "create" failed',
                          error.message)

    def test_create_deployment_timeout(self):
        self._ctx.instance.runtime_properties['deployment'] = {}
        self._ctx.instance.runtime_properties['deployment']['id'] = 'dep_name'
        self._ctx.instance.runtime_properties['deployment']['outputs'] = {}
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            list_response = cfy_mock_client.executions.list()

            list_response[0]['id'] = 'exec_id'
            list_response[0]['workflow_id'] = 'create_deployment_environment'
            list_response[0]['deployment_id'] =\
                'test_create_deployment_timeout'

            def mock_return(*args, **kwargs):
                del args, kwargs
                return list_response

            poll_with_timeout_test = \
                'cloudify_types.component.polling.poll_with_timeout'

            cfy_mock_client.executions.list = mock_return
            mock_client.return_value = cfy_mock_client
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = False
                error = self.assertRaises(
                    NonRecoverableError, create,
                    deployment_id='test_create_deployment_timeout',
                    blueprint_id='test',
                    timeout=MOCK_TIMEOUT)

                self.assertIn('Execution timeout', error.message)

    def test_create_deployment_success(self):
        self._ctx.node.properties['secrets'] = {'a': 'b'}
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            list_response = cfy_mock_client.executions.list()
            list_response[0]['id'] = 'exec_id'
            list_response[0]['workflow_id'] = 'create_deployment_environment'
            list_response[0]['deployment_id'] =\
                'test_create_deployment_success'

            def mock_return(*args, **kwargs):
                del args, kwargs
                return list_response

            poll_with_timeout_test = \
                'cloudify_types.component.polling.poll_with_timeout'

            cfy_mock_client.executions.list = mock_return
            cfy_mock_client.secrets.create = mock.Mock()
            mock_client.return_value = cfy_mock_client

            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = True

                output = create(operation='create_deployment',
                                timeout=MOCK_TIMEOUT)
                self.assertTrue(output)

            cfy_mock_client.secrets.create.assert_called_with(key='a',
                                                              value='b')

    def test_create_deployment_exists(self):
        test_name = 'test_create_deployment_exists'
        _ctx = self.get_mock_ctx(test_name)

        current_ctx.set(_ctx)
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            list_response = cfy_mock_client.deployments.list()
            list_response[0]['id'] = test_name

            def mock_return(*args, **kwargs):
                del args, kwargs
                return list_response

            cfy_mock_client.deployments.list = mock_return
            mock_client.return_value = cfy_mock_client
            output = create(operation='create_deployment',
                            timeout=MOCK_TIMEOUT)
            self.assertFalse(output)

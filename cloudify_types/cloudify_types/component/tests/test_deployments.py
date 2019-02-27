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
from ..component_operations import create_deployment, delete_deployment
from cloudify_types.component.component import DeploymentProxyBase
from .base_test_suite import DeploymentProxyTestBase, REST_CLIENT_EXCEPTION


class TestDeployment(DeploymentProxyTestBase):

    sleep_mock = None

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
        if self.sleep_mock:
            self.sleep_mock.stop()
            self.sleep_mock = None
        self.offset_patch.stop()
        self.total_patch.stop()
        super(TestDeployment, self).tearDown()

    def test_delete_deployment_rest_client_error(self):

        test_name = 'test_delete_deployment_rest_client_error'
        _ctx = self.get_mock_ctx(test_name)
        current_ctx.set(_ctx)

        _ctx.instance.runtime_properties['deployment'] = {}
        _ctx.instance.runtime_properties['deployment']['id'] = test_name
        # Tests that deployments delete fails on rest client error
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            cfy_mock_client.deployments.delete = REST_CLIENT_EXCEPTION
            mock_client.return_value = cfy_mock_client
            error = self.assertRaises(NonRecoverableError,
                                      delete_deployment,
                                      deployment_id=test_name,
                                      timeout=.01)
            self.assertIn('action delete failed',
                          error.message)

    def test_upload_plugins(self):
        # Tests that deployments upload plugins

        test_name = 'test_delete_deployment_success'
        _ctx = self.get_mock_ctx(test_name)
        current_ctx.set(_ctx)

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
                    # empty plugins
                    deployment = DeploymentProxyBase({'plugins': []})
                    deployment._upload_plugins()
                    zip_files.assert_not_called()
                    get_local_path.assert_not_called()

                    # dist of plugins
                    deployment = DeploymentProxyBase({'plugins': {
                        'base_plugin': {
                            'wagon_path': '_wagon_path',
                            'plugin_yaml_path': '_plugin_yaml_path'}}})
                    os_mock = mock.Mock()
                    with mock.patch('cloudify_types.component.component.os',
                                    os_mock):
                        deployment._upload_plugins()
                    zip_files.assert_called_with(["some_path", "some_path"])
                    get_local_path.assert_has_calls([
                        mock.call('_wagon_path', create_temp=True),
                        mock.call('_plugin_yaml_path', create_temp=True)])
                    os_mock.remove.assert_has_calls([
                        mock.call('some_path'),
                        mock.call('some_path'),
                        mock.call('_zip')])

            get_local_path = mock.Mock(return_value="some_path")
            zip_files = mock.Mock(return_value="_zip")
            with mock.patch(
                'cloudify_types.component.component.get_local_path',
                get_local_path
            ):
                zip_files = mock.Mock(return_value="_zip")
                with mock.patch(
                    'cloudify_types.component.component.zip_files',
                    zip_files
                ):
                    # list of plugins
                    deployment = DeploymentProxyBase({'plugins': [{
                            'wagon_path': '_wagon_path',
                            'plugin_yaml_path': '_plugin_yaml_path'}]})
                    os_mock = mock.Mock()
                    with mock.patch('cloudify_types.component.component.os',
                                    os_mock):
                        deployment._upload_plugins()
                    zip_files.assert_called_with(["some_path", "some_path"])
                    get_local_path.assert_has_calls([
                        mock.call('_wagon_path', create_temp=True),
                        mock.call('_plugin_yaml_path', create_temp=True)])
                    os_mock.remove.assert_has_calls([
                        mock.call('some_path'),
                        mock.call('some_path'),
                        mock.call('_zip')])

            # raise error if wrong plugins list
            deployment = DeploymentProxyBase({'plugins': True})
            error = self.assertRaises(NonRecoverableError,
                                      deployment._upload_plugins)
            self.assertIn('Wrong type in plugins: True',
                          error.message)

            # raise error if wrong wagon/yaml values
            deployment = DeploymentProxyBase({'plugins': [{
                'wagon_path': '',
                'plugin_yaml_path': ''}]})
            error = self.assertRaises(NonRecoverableError,
                                      deployment._upload_plugins)
            self.assertIn("You should provide both values wagon_path: '' "
                          "and plugin_yaml_path: ''", error.message)

    def test_delete_deployment_success(self):
        # Tests that deployments delete succeeds

        test_name = 'test_delete_deployment_success'
        _ctx = self.get_mock_ctx(test_name)
        current_ctx.set(_ctx)

        _ctx.instance.runtime_properties['deployment'] = {}
        _ctx.instance.runtime_properties['deployment']['id'] = test_name
        _ctx.instance.runtime_properties['secrets'] = {'a': 'b'}
        _ctx.instance.runtime_properties['plugins'] = ['plugin_id']

        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            cfy_mock_client.secrets.delete = mock.Mock()
            cfy_mock_client.plugins.delete = mock.Mock()
            mock_client.return_value = cfy_mock_client

            poll_with_timeout_test = \
                'cloudify_types.component.polling.poll_with_timeout'
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = True
                output = delete_deployment(
                    operation='delete_deployment',
                    deployment_id='test_deployments_delete',
                    timeout=.001)
                self.assertTrue(output)

            cfy_mock_client.secrets.delete.assert_called_with(key='a')
            cfy_mock_client.plugins.delete.assert_called_with(
                plugin_id='plugin_id')

    def test_delete_deployment_any_dep_by_id(self):
        # Tests that deployments runs any_dep_by_id
        test_name = 'test_delete_deployment_any_dep_by_id'
        _ctx = self.get_mock_ctx(test_name)
        current_ctx.set(_ctx)

        _ctx.instance.runtime_properties['deployment'] = {}
        _ctx.instance.runtime_properties['deployment']['id'] = test_name
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            mock_client.return_value = MockCloudifyRestClient()
            _ctx.instance.runtime_properties['deployment'] = {}
            _ctx.instance.runtime_properties['deployment']['id'] = test_name
            output = delete_deployment(
                operation='delete_deployment',
                deployment_id='test_deployments_delete',
                timeout=.01)
            self.assertTrue(output)

    def test_create_deployment_rest_client_error(self):
        # Tests that deployments create fails on rest client error

        test_name = 'test_create_deployment_rest_client_error'
        _ctx = self.get_mock_ctx(test_name)
        current_ctx.set(_ctx)
        _ctx.instance.runtime_properties['deployment'] = {}
        _ctx.instance.runtime_properties['deployment']['id'] = test_name
        _ctx.instance.runtime_properties['deployment']['outputs'] = {}

        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            cfy_mock_client.deployments.create = REST_CLIENT_EXCEPTION
            mock_client.return_value = cfy_mock_client
            error = self.assertRaises(NonRecoverableError,
                                      create_deployment,
                                      deployment_id='test_deployments_create',
                                      blueprint_id='test_deployments_create',
                                      timeout=.01)
            self.assertIn('action create failed',
                          error.message)

    def test_create_deployment_timeout(self):
        # Tests that deployments create fails on timeout

        test_name = 'test_create_deployment_timeout'
        _ctx = self.get_mock_ctx(test_name)
        current_ctx.set(_ctx)
        _ctx.instance.runtime_properties['deployment'] = {}
        _ctx.instance.runtime_properties['deployment']['id'] = test_name
        _ctx.instance.runtime_properties['deployment']['outputs'] = {}
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
                    NonRecoverableError, create_deployment,
                    deployment_id='test_create_deployment_timeout',
                    blueprint_id='test', timeout=.01)

                self.assertIn('Execution timeout', error.message)

    def test_create_deployment_success(self):
        # Tests that create deployment succeeds

        test_name = 'test_create_deployment_success'
        _ctx = self.get_mock_ctx(test_name)
        current_ctx.set(_ctx)

        _ctx.node.properties['secrets'] = {'a': 'b'}
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

                output = create_deployment(operation='create_deployment',
                                           timeout=.01)
                self.assertTrue(output)

            cfy_mock_client.secrets.create.assert_called_with(key='a',
                                                              value='b')

    def test_create_deployment_exists(self):
        # Tests that create deployment exists

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
            output = create_deployment(operation='create_deployment',
                                       timeout=.01)
            self.assertFalse(output)

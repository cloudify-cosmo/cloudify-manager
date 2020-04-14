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
import unittest

from cloudify.state import current_ctx
from cloudify.mocks import MockCloudifyContext

from cloudify_rest_client.exceptions import CloudifyClientError

from .client_mock import MockCloudifyRestClient

REST_CLIENT_EXCEPTION = \
    mock.MagicMock(side_effect=CloudifyClientError('Mistake'))

COMPONENT_PROPS = {
    'resource_config': {
        'blueprint': {
            'id': '',
            'blueprint_archive': 'URL',
            'main_file_name': 'blueprint.yaml'
        },
        'deployment': {
            'id': '',
            'inputs': {}
        }
    }
}

MOCK_TIMEOUT = .0001


class ComponentTestBase(unittest.TestCase):

    def setUp(self):
        super(ComponentTestBase, self).setUp()
        self._ctx = self.get_mock_ctx('test', COMPONENT_PROPS)
        self._ctx.logger.log = mock.MagicMock(return_value=None)
        self._ctx.logger.info = mock.MagicMock(return_value=None)
        current_ctx.set(self._ctx)
        self.cfy_mock_client = MockCloudifyRestClient()
        self.mock_client_patcher = mock.patch(
            'cloudify.manager.get_rest_client')
        mock_client = self.mock_client_patcher.start()
        mock_client.return_value = self.cfy_mock_client

    def tearDown(self):
        current_ctx.clear()
        self.mock_client_patcher.stop()
        super(ComponentTestBase, self).tearDown()

    @staticmethod
    def get_mock_ctx(test_name,
                     context,
                     retry_number=0):
        operation = {
            'retry_number': retry_number
        }
        ctx = MockCloudifyContext(
            node_id='node_id-{0}'.format(test_name),
            deployment_id='deployment_id-{0}'.format(test_name),
            operation=operation,
            properties=context
        )
        ctx.operation._operation_context = {'name': 'some.test'}

        return ctx

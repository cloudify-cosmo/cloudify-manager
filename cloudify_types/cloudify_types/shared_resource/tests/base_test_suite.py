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

import testtools

from cloudify.state import current_ctx
from cloudify.mocks import MockCloudifyContext

from cloudify_types.component.tests.client_mock import MockCloudifyRestClient

from ..constants import SHARED_RESOURCE_TYPE


NODE_PROPS = {
    'resource_config': {
        'deployment': {
            'id': 'test',
            'inputs': {}
        }
    }
}


class TestSharedResourceBase(testtools.TestCase):

    def setUp(self):
        super(TestSharedResourceBase, self).setUp()
        self._ctx = self.get_mock_ctx('test', SHARED_RESOURCE_TYPE)
        current_ctx.set(self._ctx)
        self.cfy_mock_client = MockCloudifyRestClient()

    def tearDown(self):
        current_ctx.clear()
        super(TestSharedResourceBase, self).tearDown()

    @staticmethod
    def get_mock_ctx(test_name,
                     mock_node_type,
                     retry_number=0,
                     node_props=NODE_PROPS):
        operation = {
            'retry_number': retry_number
        }

        ctx = MockCloudifyContext(
            node_id=test_name,
            node_name=test_name,
            node_type=mock_node_type,
            deployment_id=test_name,
            operation=operation,
            properties=node_props
        )
        ctx.operation._operation_context = {'name': 'some.test'}

        return ctx

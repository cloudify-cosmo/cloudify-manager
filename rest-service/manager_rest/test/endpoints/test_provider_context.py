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

from nose.plugins.attrib import attr

from manager_rest import manager_exceptions
from manager_rest.test import base_test
from cloudify_rest_client import exceptions


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class ProviderContextTestCase(base_test.BaseServerTestCase):

    def initialize_provider_context(self):
        pass  # each test in this class creates its own provider context

    def test_post_provider_context(self):
        result = self.client.manager.create_context(
            'test_provider',
            {'key': 'value'})
        self.assertEqual('ok', result['status'])

    def test_get_provider_context(self):
        self.test_post_provider_context()
        result = self.get('/provider/context').json
        self.assertEqual(result['context']['key'], 'value')
        self.assertEqual(result['name'], 'test_provider')

    def test_post_provider_context_twice_fails(self):
        self.test_post_provider_context()
        try:
            self.test_post_provider_context()
            self.fail('Expected failure when trying to re-post provider '
                      'context')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(409, e.status_code)
            self.assertEqual(
                manager_exceptions.ConflictError.CONFLICT_ERROR_CODE,
                e.error_code)

    def test_update_provider_context(self):
        self.test_post_provider_context()
        new_context = {'key': 'new-value'}
        self.client.manager.update_context(
            'test_provider', new_context)
        context = self.client.manager.get_context()
        self.assertEqual(context['context'], new_context)

    def test_update_empty_provider_context(self):
        try:
            self.client.manager.update_context(
                'test_provider',
                {'key': 'value'})
            self.fail('Expected failure due to nonexisting context')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(e.status_code, 404)
            self.assertEqual(e.message, 'Provider Context not found')

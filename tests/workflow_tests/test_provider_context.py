########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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


from cloudify_rest_client.exceptions import CloudifyClientError
from testenv import TestCase
from testenv import utils
from testenv.utils import PROVIDER_NAME
from testenv.utils import PROVIDER_CONTEXT


class TestProviderContext(TestCase):

    def test_provider_context(self):
        # Context is already setup during test bootstrap phase,
        # we only verify everything was properly saved and accessible
        name = PROVIDER_NAME
        context = PROVIDER_CONTEXT
        response_context = self.client.manager.get_context()
        self.assertEqual(name, response_context['name'])
        self.assertEqual(context, response_context['context'])
        self.assertRaises(CloudifyClientError,
                          self.client.manager.create_context, name, context)

    def test_update_provider_context(self):
        try:
            self.client.manager.update_context(
                'test_update_provider_context', PROVIDER_CONTEXT)
            context = self.client.manager.get_context()
            self.assertEqual('test_update_provider_context',
                             context['name'])
            self.assertEqual(PROVIDER_CONTEXT, context['context'])
        finally:
            # re-create provider context to the previous value
            # perhaps other tests rely on these values.
            utils.restore_provider_context()

    def test_update_empty_provider_context(self):
        try:
            utils.delete_provider_context()
            self.client.manager.update_context(
                'test_update_provider_context',
                PROVIDER_CONTEXT)
            self.fail('Expected failure due to existing context')
        except CloudifyClientError as e:
            self.assertEqual(e.status_code, 404)
            self.assertEqual(e.message, 'Provider Context not found')
        finally:
            # re-create provider context to the previous value
            # perhaps other tests rely on these values.
            utils.restore_provider_context()

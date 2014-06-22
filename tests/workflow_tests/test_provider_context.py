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

__author__ = 'dank'

from cloudify_rest_client.exceptions import CloudifyClientError
from testenv import (TestCase,
                     PROVIDER_NAME,
                     PROVIDER_CONTEXT)


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

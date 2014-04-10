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

from cosmo_manager_rest_client.cosmo_manager_rest_client import \
    CosmoManagerRestCallError

from testenv import TestCase
from testenv import post_provider_context
from testenv import get_provider_context


class TestProviderContext(TestCase):

    def test_provider_context(self):
        name = 'test_provider'
        context = {
            'key1': 'value1',
            'key2': 'value2'
        }
        post_response = post_provider_context(name, context)
        self.assertEqual(post_response.status, 'ok')
        response_context = get_provider_context()
        self.assertEqual(name, response_context['name'])
        self.assertEqual(context, response_context['context'])
        self.assertRaises(CosmoManagerRestCallError,
                          post_provider_context, name, context)

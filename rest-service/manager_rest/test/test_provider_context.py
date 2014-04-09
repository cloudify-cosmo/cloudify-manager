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

__author__ = 'dan'


from base_test import BaseServerTestCase


class ProviderContextTestCase(BaseServerTestCase):

    def test_post_provider_context(self):
        result = self.post('/provider/context', data={
            'provider': 'test_provider',
            'context': {'key': 'value'}
        })
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json['status'], 'ok')

    def test_get_provider_context(self):
        self.test_post_provider_context()
        result = self.get('/provider/context').json
        self.assertEqual(result['context']['key'], 'value')
        self.assertEqual(result['provider'], 'test_provider')

    def test_post_provider_context_twice_fails(self):
        self.test_post_provider_context()
        self.assertRaises(self.failureException,
                          self.test_post_provider_context)

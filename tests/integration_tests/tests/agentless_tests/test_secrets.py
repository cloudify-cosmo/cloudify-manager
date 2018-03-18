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

from integration_tests import AgentlessTestCase
from cloudify_rest_client.exceptions import CloudifyClientError


class SecretsTest(AgentlessTestCase):

    def test_create_encrypted_secret(self):
        new_secret = self.client.secrets.create('test_key', 'test_value')
        self.assertNotEqual('test_value', new_secret.value)

    def test_get_decrypted_secret(self):
        new_secret = self.client.secrets.create('test_key', 'test_value')
        received_secret = self.client.secrets.get(new_secret.key)
        self.assertEqual(received_secret.key, new_secret.key)
        self.assertEqual(received_secret.value, 'test_value')

    def test_get_secret_not_found(self):
        self.assertRaisesRegexp(
            CloudifyClientError,
            '404: Requested `Secret` with ID `test_key` was not found',
            self.client.secrets.get,
            'test_key'
        )

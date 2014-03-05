########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'ran'

from testenv import TestCase
from cosmo_manager_rest_client.cosmo_manager_rest_client \
    import CosmoManagerRestClient, CosmoManagerRestCallError


class TestStorage(TestCase):

    def test_update_node_bad_version(self):
        client = CosmoManagerRestClient('localhost')

        node_id = '1'
        state_version = 1
        result = client.put_node_state(node_id, {})
        self.assertEquals(state_version, result['stateVersion'])
        self.assertEquals('1', result['id'])
        self.assertEquals({}, result['runtimeInfo'])

        result = client.update_node_state(node_id, {}, state_version)
        self.assertEquals(2, result['stateVersion'])
        self.assertEquals('1', result['id'])
        self.assertEquals({}, result['runtimeInfo'])

        #making another call with a bad state_version
        self.assertRaises(
            CosmoManagerRestCallError, client.update_node_state,
            node_id, {}, state_version)

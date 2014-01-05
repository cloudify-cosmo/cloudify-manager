#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'idanmo'

from base_test import BaseServerTestCase


class NodesTest(BaseServerTestCase):

    def test_get_node(self):
        response = self.get('/nodes/1234').json
        self.assertEqual('1234', response['id'])
        self.assertTrue('runtimeInfo' in response)
        self.assertEqual(0, len(response['runtimeInfo']))

    def test_put_new_node(self):
        response = self.put('/nodes/1234', {'key': 'value'})
        self.assertEqual(200, response.status_code)
        self.assertEqual('1234', response.json['id'])
        self.assertEqual(1, len(response.json['runtimeInfo']))
        self.assertEqual('value', response.json['runtimeInfo']['key'])

    def test_put_update_node(self):
        self.put('/nodes/1234', {'key': 'value'})
        response = self.put('/nodes/1234', {'key': 'value2', 'aaa': 'bbb'})
        self.assertEqual(200, response.status_code)
        self.assertEqual('1234', response.json['id'])
        self.assertEqual(2, len(response.json['runtimeInfo']))
        self.assertEqual('value2', response.json['runtimeInfo']['key'])
        self.assertEqual('bbb', response.json['runtimeInfo']['aaa'])
        response = self.put('/nodes/1234', {})
        self.assertEqual(200, response.status_code)
        self.assertEqual('1234', response.json['id'])
        self.assertEqual(0, len(response.json['runtimeInfo']))

    def test_get_nodes(self):
        response = self.get('/nodes')
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.json['nodes']))
        self.put('/nodes/1', {'key': 'value'})
        self.put('/nodes/2', {'key': 'value'})
        response = self.get('/nodes')
        ids = map(lambda x: x['id'], response.json['nodes'])
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(ids))
        self.assertTrue('1' in ids)
        self.assertTrue('2' in ids)

    def test_patch_node(self):
        self.put('/nodes/1234', {'key': 'value'})
        update = {'key': ['new_value', 'value'], 'new_key': ['value']}
        response = self.patch('/nodes/1234', update)
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json['runtimeInfo']))
        self.assertEqual('new_value', response.json['runtimeInfo']['key'])
        self.assertEqual('value', response.json['runtimeInfo']['new_key'])
        response = self.get('/nodes/1234')
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json['runtimeInfo']))
        self.assertEqual('new_value', response.json['runtimeInfo']['key'])
        self.assertEqual('value', response.json['runtimeInfo']['new_key'])

    def test_patch_node_conflict(self):
        response = self.patch('/nodes/1234', {'key': ['new_value', 'old_value']})
        self.assertEqual(500, response.status_code)
        self.put('/nodes/1234', {'key': 'value'})
        response = self.patch('/nodes/1234', {'key': ['new_value', 'old_value']})
        self.assertEqual(500, response.status_code)

    def test_invalid_input(self):
        response = self.patch('/nodes/1234', [])
        self.assertEqual(400, response.status_code)
        response = self.patch('/nodes/1234', {'key': None})
        self.assertEqual(400, response.status_code)
        response = self.patch('/nodes/1234', {'key': 'value'})
        self.assertEqual(400, response.status_code)
        response = self.patch('/nodes/1234', {'key': ['1', '2', '3']})
        self.assertEqual(400, response.status_code)

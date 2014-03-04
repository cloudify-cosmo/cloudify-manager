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

    def test_bad_patch_node(self):
        #just a bunch of bad calls to patch node
        response = self.patch('/nodes/1234', 'not a dictionary')
        self.assertEqual(400, response.status_code)
        response = self.patch('/nodes/1234', {'a dict': 'without runtime_info'
                                                        ' key'})
        self.assertEqual(400, response.status_code)
        response = self.patch('/nodes/1234', {'a dict': 'without '
                                                        'state_version key'})
        self.assertEqual(400, response.status_code)
        response = self.patch('/nodes/1234', {'runtime_info': {},
                                              'state_version': 0,
                                              'extra_prop': 'is bad'})
        self.assertEqual(400, response.status_code)
        response = self.patch('/nodes/1234', {'runtime_info': {},
                                              'state_version': 'not an int'})
        self.assertEqual(400, response.status_code)
        response = self.patch('/nodes/1234', {'runtime_info': 'not a dict',
                                              'state_version': 0})
        self.assertEqual(400, response.status_code)

    def test_patch_node(self):
        self.put('/nodes/1234', {'key': 'value'})
        update = {'runtime_info': {'key': 'new_value', 'new_key': 'value'},
                  'state_version': 2}
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

    def test_patch_node_merge(self):
        self.put('/nodes/1234', {'key': 'value'})
        response = self.patch('/nodes/1234', {'runtime_info': {'aaa': 'bbb'},
                                              'state_version': 2})
        self.assertEqual(200, response.status_code)
        self.assertEqual('1234', response.json['id'])
        self.assertEqual(2, len(response.json['runtimeInfo']))
        self.assertEqual('value', response.json['runtimeInfo']['key'])
        self.assertEqual('bbb', response.json['runtimeInfo']['aaa'])

    def test_patch_node_conflict(self):
        import manager_rest.storage_manager as sm
        from manager_rest import manager_exceptions
        prev_update_node_func = sm.instance().update_node
        try:
            def conflict_update_node_func(node_id, node):
                raise manager_exceptions.ConflictError()
            sm.instance().update_node = conflict_update_node_func
            self.put('/nodes/1234', {'key': 'value'})
            response = self.patch('/nodes/1234', {'runtime_info': {'key': ' \
                                                               ''new_value'},
                                                  'state_version': 2})
            self.assertEqual(409, response.status_code)
        finally:
            sm.instance().update_node = prev_update_node_func

    def test_patch_before_put(self):
        response = self.patch('/nodes/1234',
                              {'runtime_info': {'key': 'value'},
                               'state_version': 0})
        self.assertEqual(404, response.status_code)

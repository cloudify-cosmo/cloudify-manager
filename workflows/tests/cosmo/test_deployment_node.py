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

__author__ = 'idanmo'


import unittest
from cloudify.manager import DeploymentNode


class TestDeploymentNode(unittest.TestCase):

    def test_no_updates_to_empty_node(self):
        node = DeploymentNode('id', None)
        self.assertEqual(0, len(node.get_updated_properties()))

    def test_no_updates(self):
        node = DeploymentNode('id', {'key': 'value'})
        self.assertEqual(0, len(node.get_updated_properties()))

    def test_put_new_property(self):
        node = DeploymentNode('id', None)
        node.put('key', 'value')
        self.assertEqual('value', node.get('key'))
        updated = node.get_updated_properties()
        self.assertEqual(1, len(updated))
        self.assertEqual(1, len(updated['key']))
        self.assertEqual('value', updated['key'][0])

    def test_put_several_properties(self):
        node = DeploymentNode('id', {'key0': 'value0'})
        node.put('key1', 'value1')
        node.put('key2', 'value2')
        updated = node.get_updated_properties()
        self.assertEqual(2, len(updated))
        self.assertEqual(1, len(updated['key1']))
        self.assertEqual(1, len(updated['key2']))
        self.assertEqual('value1', updated['key1'][0])
        self.assertEqual('value2', updated['key2'][0])

    def test_put_new_property_twice(self):
        node = DeploymentNode('id', None)
        node.put('key', 'value')
        node.put('key', 'v')
        self.assertEqual('v', node.get('key'))
        updated = node.get_updated_properties()
        self.assertEqual(1, len(updated))
        self.assertEqual(2, len(updated['key']))
        self.assertEqual('v', updated['key'][0])
        self.assertEqual('value', updated['key'][1])

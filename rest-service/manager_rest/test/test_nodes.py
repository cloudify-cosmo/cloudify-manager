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

import manager_rest.storage_manager as sm
from base_test import BaseServerTestCase


class NodesTest(BaseServerTestCase):

    def test_get_nonexisting_node(self):
        response = self.get('/node-instances/1234')
        self.assertEqual(404, response.status_code)

    def test_get_node(self):
        self.put_node_instance(
            instance_id='1234',
            deployment_id='111',
            runtime_properties={
                'key': 'value'
            }
        )
        response = self.get('/node-instances/1234')
        self.assertEqual(200, response.status_code)
        self.assertEqual('1234', response.json['id'])
        self.assertTrue('runtime_properties' in response.json)
        self.assertEqual(1, len(response.json['runtime_properties']))
        self.assertEqual('value', response.json['runtime_properties']['key'])

    def test_bad_patch_node(self):
        # just a bunch of bad calls to patch node
        response = self.patch('/node-instances/1234', 'not a dictionary')
        self.assertEqual(400, response.status_code)
        response = self.patch('/node-instances/1234', {
            'a dict': 'without '
                      'state_version'
                      ' key'})
        self.assertEqual(400, response.status_code)
        response = self.patch('/node-instances/1234', {
            'runtime_properties': {},
            'version': 'not an int'})
        self.assertEqual(400, response.status_code)

    def test_patch_node(self):
        self.put_node_instance(
            instance_id='1234',
            deployment_id='111',
            runtime_properties={
                'key': 'value'
            }
        )
        update = {
            'runtime_properties': {'key': 'new_value', 'new_key': 'value'},
            'version': 2}
        response = self.patch('/node-instances/1234', update)
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json['runtime_properties']))
        self.assertEqual('new_value',
                         response.json['runtime_properties']['key'])
        self.assertEqual('value',
                         response.json['runtime_properties']['new_key'])
        response = self.get('/node-instances/1234')

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json['runtime_properties']))
        self.assertEqual('new_value',
                         response.json['runtime_properties']['key'])
        self.assertEqual('value',
                         response.json['runtime_properties']['new_key'])

    def test_patch_node_runtime_props_update(self):
        self.put_node_instance(
            instance_id='1234',
            deployment_id='111',
            runtime_properties={
                'key': 'value'
            }
        )
        response = self.patch('/node-instances/1234', {
            'runtime_properties': {'aaa': 'bbb'},
            'version': 2})
        self.assertEqual(200, response.status_code)
        self.assertEqual('1234', response.json['id'])
        self.assertEqual(1, len(response.json['runtime_properties']))
        self.assertEqual('bbb', response.json['runtime_properties']['aaa'])

    def test_patch_node_runtime_props_overwrite(self):
        self.put_node_instance(
            instance_id='1234',
            deployment_id='111',
            runtime_properties={
                'key': 'value'
            }
        )
        response = self.patch('/node-instances/1234', {
            'runtime_properties': {'key': 'value2'},
            'version': 2})
        self.assertEqual(200, response.status_code)
        self.assertEqual('1234', response.json['id'])
        self.assertEqual(1, len(response.json['runtime_properties']))
        self.assertEqual('value2', response.json['runtime_properties']['key'])

    def test_patch_node_runtime_props_cleanup(self):
        self.put_node_instance(
            instance_id='1234',
            deployment_id='111',
            runtime_properties={
                'key': 'value'
            }
        )
        response = self.patch('/node-instances/1234', {
            'runtime_properties': {},
            'version': 2})
        self.assertEqual(200, response.status_code)
        self.assertEqual('1234', response.json['id'])
        self.assertEqual(0, len(response.json['runtime_properties']))

    def test_partial_patch_node(self):
        self.put_node_instance(
            instance_id='1234',
            deployment_id='111',
            runtime_properties={
                'key': 'value'
            }
        )

        # full patch
        response = self.patch('/node-instances/1234',
                              {
                                  'state': 'a-state',
                                  'runtime_properties': {'aaa': 'bbb'},
                                  'version': 2
                              })
        self.assertEqual(200, response.status_code)
        self.assertEqual('bbb', response.json['runtime_properties']['aaa'])
        self.assertEqual('a-state', response.json['state'])

        # patch with no runtime properties
        response = self.patch('/node-instances/1234', {'state': 'b-state',
                                                       'version': 3})
        self.assertEqual(200, response.status_code)
        self.assertEqual('bbb', response.json['runtime_properties']['aaa'])
        self.assertEqual('b-state', response.json['state'])

        # patch with neither state nor runtime properties
        response = self.patch('/node-instances/1234', {'version': 4})
        self.assertEqual(200, response.status_code)
        self.assertEqual('bbb', response.json['runtime_properties']['aaa'])
        self.assertEqual('b-state', response.json['state'])

        # patch with no state
        response = self.patch('/node-instances/1234',
                              {
                                  'runtime_properties': {'ccc': 'ddd'},
                                  'version': 5
                              })
        self.assertEqual(200, response.status_code)
        self.assertEqual('ddd', response.json['runtime_properties']['ccc'])
        self.assertEqual('b-state', response.json['state'])

    def test_patch_node_conflict(self):
        from manager_rest import manager_exceptions
        prev_update_node_func = sm.instance().update_node_instance
        try:
            def conflict_update_node_func(node):
                raise manager_exceptions.ConflictError()
            sm.instance().update_node_instance = conflict_update_node_func
            self.put_node_instance(
                instance_id='1234',
                deployment_id='111',
                runtime_properties={
                    'key': 'value'
                }
            )
            response = self.patch('/node-instances/1234',
                                  {'runtime_properties': {'key': 'new_value'},
                                   'version': 2})
            self.assertEqual(409, response.status_code)
        finally:
            sm.instance().update_node_instance = prev_update_node_func

    def test_list_node_instances(self):
        self.put_node_instance(node_id='1', instance_id='11',
                               deployment_id='111')
        self.put_node_instance(node_id='1', instance_id='12',
                               deployment_id='111')
        self.put_node_instance(node_id='2', instance_id='21',
                               deployment_id='111')
        self.put_node_instance(node_id='2', instance_id='22',
                               deployment_id='111')
        self.put_node_instance(node_id='3', instance_id='31',
                               deployment_id='222')
        self.put_node_instance(node_id='3', instance_id='32',
                               deployment_id='222')
        self.put_node_instance(node_id='4', instance_id='41',
                               deployment_id='222')
        self.put_node_instance(node_id='4', instance_id='42',
                               deployment_id='222')

        all_instances = self.client.node_instances.list()
        dep1_instances = self.client.node_instances.list('111')
        dep2_instances = self.client.node_instances.list('222')
        dep1_n1_instances = self.client.node_instances.list('111', '1')
        dep1_n2_instances = self.client.node_instances.list('111', '2')
        dep2_n3_instances = self.client.node_instances.list('222', '3')
        dep2_n4_instances = self.client.node_instances.list('222', '4')

        self.assertEqual(8, len(all_instances))

        def assert_dep(expected_len, dep, instances):
            self.assertEqual(expected_len, len(instances))
            for instance in instances:
                self.assertEqual(instance.deployment_id, dep)

        assert_dep(4, '111', dep1_instances)
        assert_dep(4, '222', dep2_instances)

        def assert_dep_and_node(expected_len, dep, node_id, instances):
            self.assertEqual(expected_len, len(instances))
            for instance in instances:
                self.assertEqual(instance.deployment_id, dep)
                self.assertEqual(instance.node_id, node_id)

        assert_dep_and_node(2, '111', '1', dep1_n1_instances)
        assert_dep_and_node(2, '111', '2', dep1_n2_instances)
        assert_dep_and_node(2, '222', '3', dep2_n3_instances)
        assert_dep_and_node(2, '222', '4', dep2_n4_instances)

    def test_patch_before_put(self):
        response = self.patch('/node-instances/1234',
                              {'runtime_properties': {'key': 'value'},
                               'version': 0})
        self.assertEqual(404, response.status_code)

    def put_node_instance(self,
                          instance_id,
                          deployment_id,
                          runtime_properties=None,
                          node_id=None):
        runtime_properties = runtime_properties or {}
        from manager_rest.models import DeploymentNodeInstance
        node = DeploymentNodeInstance(id=instance_id,
                                      node_id=node_id,
                                      deployment_id=deployment_id,
                                      runtime_properties=runtime_properties,
                                      state=None,
                                      version=None,
                                      relationships=None,
                                      host_id=None)
        sm.instance().put_node_instance(node)

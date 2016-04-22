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

from nose.plugins.attrib import attr

from cloudify_rest_client.exceptions import CloudifyClientError
from manager_rest import manager_exceptions
from manager_rest import storage_manager
from manager_rest.test import base_test


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class NodesTest(base_test.BaseServerTestCase):
    """Test the HTTP interface and the behaviour of node instance endpoints.

    Test cases that test the HTTP interface use shorthand methods like .patch()
    or .get() to call the rest service endpoints with hand-crafted data.
    Test cases that verify the behaviour use the rest client to construct
    the requests.
    """

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
        """Malformed node instance update requests return an error."""
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

    def test_partial_patch_node(self):
        """PATCH requests with partial data are accepted."""
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

    def test_old_version(self):
        """Can't update a node instance passing new version <= old version."""
        node_instance_id = '1234'
        self.put_node_instance(
            instance_id=node_instance_id,
            deployment_id='111',
            runtime_properties={
                'key': 'value'
            },
            version=1
        )

        with self.assertRaises(CloudifyClientError) as cm:
            self.client.node_instances.update(
                node_instance_id,
                version=1,
                runtime_properties={'key': 'new value'})
        self.assertEqual(cm.exception.status_code, 409)

    def test_patch_node(self):
        """Getting an instance after updating it, returns the updated data."""
        node_instance_id = '1234'
        self.put_node_instance(
            instance_id=node_instance_id,
            deployment_id='111',
            runtime_properties={
                'key': 'value'
            }
        )
        response = self.client.node_instances.update(
            node_instance_id,
            runtime_properties={'key': 'new_value', 'new_key': 'value'},
            version=2)

        self.assertEqual(2, len(response.runtime_properties))
        self.assertEqual('new_value', response.runtime_properties['key'])
        self.assertEqual('value', response.runtime_properties['new_key'])

        response = self.client.node_instances.get(node_instance_id)

        self.assertEqual(2, len(response.runtime_properties))
        self.assertEqual('new_value', response.runtime_properties['key'])
        self.assertEqual('value', response.runtime_properties['new_key'])

    def test_patch_node_runtime_props_update(self):
        """Sending new runtime properties overwrites existing ones.

        The new runtime properties dict is stored as is, not merged with
        preexisting runtime properties.
        """
        node_instance_id = '1234'
        self.put_node_instance(
            instance_id=node_instance_id,
            deployment_id='111',
            runtime_properties={
                'key': 'value'
            }
        )

        response = self.client.node_instances.update(
            node_instance_id,
            runtime_properties={'aaa': 'bbb'},
            version=2)

        self.assertEqual('1234', response.id)
        self.assertEqual(1, len(response.runtime_properties))
        self.assertEqual('bbb', response.runtime_properties['aaa'])
        self.assertNotIn('key', response.runtime_properties)

    def test_patch_node_runtime_props_overwrite(self):
        """Runtime properties update with a preexisting key keeps the new value.

        When the new runtime properties have a key that was already in
        runtime properties, the new value wins.
        """
        node_instance_id = '1234'
        self.put_node_instance(
            instance_id=node_instance_id,
            deployment_id='111',
            runtime_properties={
                'key': 'value'
            }
        )
        response = self.client.node_instances.update(
            node_instance_id,
            runtime_properties={'key': 'value2'},
            version=2)
        self.assertEqual('1234', response.id)
        self.assertEqual(1, len(response.runtime_properties))
        self.assertEqual('value2', response.runtime_properties['key'])

    def test_patch_node_runtime_props_cleanup(self):
        """Sending empty runtime properties, removes preexisting ones."""
        node_instance_id = '1234'
        self.put_node_instance(
            instance_id=node_instance_id,
            deployment_id='111',
            runtime_properties={
                'key': 'value'
            }
        )
        response = self.client.node_instances.update(
            node_instance_id,
            runtime_properties={},
            version=2)
        self.assertEqual('1234', response['id'])
        self.assertEqual(0, len(response['runtime_properties']))

    def test_patch_node_conflict(self):
        """A conflict inside the storage manager propagates to the client."""
        # patch the storage manager .update_node_instance method to throw an
        # error - remember to revert it after the test
        sm = storage_manager._get_instance()

        def _revert_update_node_func(sm, func):
            sm.update_node_instance = func

        def conflict_update_node_func(node):
            raise manager_exceptions.ConflictError()

        self.addCleanup(_revert_update_node_func, sm, sm.update_node_instance)
        sm.update_node_instance = conflict_update_node_func

        node_instance_id = '1234'
        self.put_node_instance(
            instance_id=node_instance_id,
            deployment_id='111',
            runtime_properties={
                'key': 'value'
            }
        )

        with self.assertRaises(CloudifyClientError) as cm:
            self.client.node_instances.update(
                node_instance_id,
                runtime_properties={'key': 'new_value'},
                version=2)

        self.assertEqual(cm.exception.status_code, 409)

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_list_node_instances_multiple_value_filter(self):
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
        dep1_node_instances = \
            self.client.node_instances.list('111', ['1', '2', '3', '4'])

        self.assertEqual(8, len(all_instances))
        self.assertEquals(4, len(dep1_node_instances))

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
        """Updating a nonexistent node instance throws an error."""
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.node_instances.update(
                '1234',
                runtime_properties={'key': 'value'},
                version=0)

        self.assertEqual(cm.exception.status_code, 404)

    def put_node_instance(self,
                          instance_id,
                          deployment_id,
                          runtime_properties=None,
                          node_id=None,
                          version=None):
        runtime_properties = runtime_properties or {}
        from manager_rest.models import DeploymentNodeInstance
        node = DeploymentNodeInstance(id=instance_id,
                                      node_id=node_id,
                                      deployment_id=deployment_id,
                                      runtime_properties=runtime_properties,
                                      state=None,
                                      version=version,
                                      relationships=None,
                                      host_id=None)
        storage_manager._get_instance().put_node_instance(node)

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

import mock

from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.storage import db, models
from manager_rest.test import base_test
from manager_rest import manager_exceptions


class _NodeSetupMixin(object):
    """A mixin useful in these tests, that exposes utils for creating nodes

    Creating nodes otherwise is a pain because of how many arguments
    they require
    """
    def setUp(self):
        super().setUp()
        self.bp1 = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )
        self.dep1 = self._deployment('d1')

    def _deployment(self, deployment_id, **kwargs):
        deployment_params = {
            'id': deployment_id,
            'blueprint': self.bp1,
            'scaling_groups': {},
            'creator': self.user,
            'tenant': self.tenant,
        }
        deployment_params.update(kwargs)
        return models.Deployment(**deployment_params)

    def _node(self, node_id, **kwargs):
        node_params = {
            'id': node_id,
            'type': 'type1',
            'number_of_instances': 0,
            'deploy_number_of_instances': 0,
            'max_number_of_instances': 0,
            'min_number_of_instances': 0,
            'planned_number_of_instances': 0,
            'deployment': self.dep1,
            'creator': self.user,
            'tenant': self.tenant,
        }
        node_params.update(kwargs)
        return models.Node(**node_params)

    def _instance(self, instance_id, **kwargs):
        instance_params = {
            'id': instance_id,
            'state': '',
            'creator': self.user,
            'tenant': self.tenant,
        }
        instance_params.update(kwargs)
        if 'node' not in instance_params:
            instance_params['node'] = self._node('node1')
        return models.NodeInstance(**instance_params)


class NodesTest(_NodeSetupMixin, base_test.BaseServerTestCase):
    """Test the HTTP interface and the behaviour of node instance endpoints.

    Test cases that test the HTTP interface use shorthand methods like .patch()
    or .get() to call the rest service endpoints with hand-crafted data.
    Test cases that verify the behaviour use the rest client to construct
    the requests.
    """
    def test_get_nonexisting_node(self):
        response = self.get('/node-instances/1234')
        self.assertEqual(404, response.status_code)

    def test_get_instance(self):
        self._instance(
            '1234',
            runtime_properties={'key': 'value'},
        )
        response = self.get('/node-instances/1234')
        assert response.status_code == 200
        assert response.json['id'] == '1234'
        assert response.json['runtime_properties'] == {'key': 'value'}

    def test_sort_nodes_list(self):
        dep2 = models.Deployment(
            id='d2',
            blueprint=self.bp1,
            scaling_groups={},
            creator=self.user,
            tenant=self.tenant,
        )
        db.session.add(dep2)
        self._node('node1')
        self._node('node2', deployment=dep2)

        nodes = self.client.nodes.list(sort='deployment_id')
        assert [n.id for n in nodes] == ['node1', 'node2']

        nodes = self.client.nodes.list(sort='deployment_id',
                                       is_descending=True)
        assert [n.id for n in nodes] == ['node2', 'node1']

    def test_bad_patch_node(self):
        """Malformed node instance update requests return an error."""
        response = self.patch('/node-instances/1234', 'not a dictionary')
        assert response.status_code == 400
        response = self.patch('/node-instances/1234', {
            'a dict': 'without a version key'
        })
        assert response.status_code == 400
        response = self.patch('/node-instances/1234', {
            'runtime_properties': {},
            'version': 'not an int'})
        assert response.status_code == 400

    def test_partial_patch_node(self):
        """PATCH requests with partial data are accepted."""
        self._instance(
            '1234',
            runtime_properties={'key': 'value'},
        )
        # full patch
        response = self.patch('/node-instances/1234',
                              {
                                  'state': 'a-state',
                                  'runtime_properties': {'aaa': 'bbb'},
                                  'version': 1
                              })
        assert response.status_code == 200
        assert response.json['runtime_properties']['aaa'] == 'bbb'
        assert response.json['state'] == 'a-state'

        # patch with no runtime properties
        response = self.patch('/node-instances/1234', {'state': 'b-state',
                                                       'version': 2})
        assert response.status_code == 200
        assert response.json['runtime_properties']['aaa'] == 'bbb'
        assert response.json['state'] == 'b-state'

        # patch with neither state nor runtime properties
        response = self.patch('/node-instances/1234', {'version': 3})
        assert response.status_code == 200
        assert response.json['runtime_properties']['aaa'] == 'bbb'
        assert response.json['state'] == 'b-state'

        # patch with no state
        response = self.patch('/node-instances/1234',
                              {
                                  'runtime_properties': {'ccc': 'ddd'},
                                  'version': 4
                              })
        assert response.status_code == 200
        assert response.json['runtime_properties']['ccc'] == 'ddd'
        assert response.json['state'] == 'b-state'

    def test_old_version(self):
        """Can't update a node instance passing new version != old version."""
        ni = self._instance('1234')
        # commit to get sqlalchemy to actually write the version field
        db.session.commit()
        ni.version = 5

        with self.assertRaises(CloudifyClientError) as cm:
            self.client.node_instances.update(
                '1234',
                version=2,  # Expecting version==5
                runtime_properties={'key': 'new value'})
        assert cm.exception.status_code == 409

    def test_patch_node(self):
        """Getting an instance after updating it, returns the updated data."""
        node_instance_id = '1234'
        self._instance(
            node_instance_id,
            runtime_properties={'key': 'value'},
        )

        response = self.client.node_instances.update(
            node_instance_id,
            runtime_properties={'key': 'new_value', 'new_key': 'value'}
        )

        assert len(response.runtime_properties) == 2
        assert response.runtime_properties['key'] == 'new_value'
        assert response.runtime_properties['new_key'] == 'value'

        response = self.client.node_instances.get(node_instance_id)

        assert len(response.runtime_properties) == 2
        assert response.runtime_properties['key'] == 'new_value'
        assert response.runtime_properties['new_key'] == 'value'

    def test_patch_node_runtime_props_update(self):
        """Sending new runtime properties overwrites existing ones.

        The new runtime properties dict is stored as is, not merged with
        preexisting runtime properties.
        """
        node_instance_id = '1234'
        self._instance(
            node_instance_id,
            runtime_properties={'key': 'value'},
        )

        response = self.client.node_instances.update(
            node_instance_id,
            runtime_properties={'aaa': 'bbb'}
        )

        assert response.id == '1234'
        assert len(response.runtime_properties) == 1
        assert response.runtime_properties['aaa'] == 'bbb'
        self.assertNotIn('key', response.runtime_properties)

    def test_patch_node_runtime_props_overwrite(self):
        """Runtime properties update with a preexisting key keeps the new value.

        When the new runtime properties have a key that was already in
        runtime properties, the new value wins.
        """
        node_instance_id = '1234'
        self._instance(
            node_instance_id,
            runtime_properties={'key': 'value'},
        )

        response = self.client.node_instances.update(
            node_instance_id,
            runtime_properties={'key': 'value2'}
        )
        assert response.id == '1234'
        assert len(response.runtime_properties) == 1
        assert response.runtime_properties['key'] == 'value2'

    def test_patch_node_runtime_props_cleanup(self):
        """Sending empty runtime properties, removes preexisting ones."""
        node_instance_id = '1234'
        self._instance(
            node_instance_id,
            runtime_properties={'key': 'value'},
        )
        response = self.client.node_instances.update(
            node_instance_id,
            runtime_properties={}
        )
        assert response['id'] == '1234'
        assert len(response['runtime_properties']) == 0

    def test_patch_node_conflict(self):
        """A conflict inside the storage manager propagates to the client."""
        node_instance_id = '1234'
        self._instance(
            node_instance_id,
            runtime_properties={'key': 'value'},
        )

        with mock.patch(
            'manager_rest.storage.storage_manager.SQLStorageManager.update',
            side_effect=manager_exceptions.ConflictError
        ):
            with self.assertRaises(CloudifyClientError) as cm:
                self.client.node_instances.update(
                    node_instance_id,
                    runtime_properties={'key': 'new_value'},
                    version=2
                )

        assert cm.exception.status_code == 409

    def test_list_node_instances_multiple_value_filter(self):
        dep2 = self._deployment('d2')
        node1 = self._node('1', deployment=self.dep1)
        node2 = self._node('2', deployment=self.dep1)
        node3 = self._node('3', deployment=dep2)
        node4 = self._node('4', deployment=dep2)
        self._instance('11', node=node1)
        self._instance('12', node=node1)
        self._instance('21', node=node2)
        self._instance('22', node=node2)
        self._instance('31', node=node3)
        self._instance('32', node=node3)
        self._instance('41', node=node4)
        self._instance('44', node=node4)

        all_instances = self.client.node_instances.list()
        dep1_node_instances = \
            self.client.node_instances.list(
                deployment_id=self.dep1.id,
                node_id=['1', '2', '3', '4']
            )

        assert len(all_instances) == 8
        assert len(dep1_node_instances) == 4

    def test_list_node_instances(self):
        dep2 = self._deployment('d2')
        node1 = self._node('1', deployment=self.dep1)
        node2 = self._node('2', deployment=self.dep1)
        node3 = self._node('3', deployment=dep2)
        node4 = self._node('4', deployment=dep2)
        self._instance('11', node=node1)
        self._instance('12', node=node1)
        self._instance('21', node=node2)
        self._instance('22', node=node2)
        self._instance('31', node=node3)
        self._instance('32', node=node3)
        self._instance('41', node=node4)
        self._instance('44', node=node4)

        all_instances = self.client.node_instances.list()
        dep1_instances = self.client.node_instances.list(
            deployment_id=self.dep1.id)
        dep2_instances = self.client.node_instances.list(
            deployment_id=dep2.id)
        dep1_n1_instances = self.client.node_instances.list(
            deployment_id=self.dep1.id,
            node_id='1'
        )
        dep1_n2_instances = self.client.node_instances.list(
            deployment_id=self.dep1.id,
            node_id='2'
        )
        dep2_n3_instances = self.client.node_instances.list(
            deployment_id=dep2.id,
            node_id='3'
        )
        dep2_n4_instances = self.client.node_instances.list(
            deployment_id=dep2.id,
            node_id='4'
        )

        assert len(all_instances) == 8
        assert len(dep1_instances) == 4
        assert len(dep2_instances) == 4
        assert all(ni.deployment_id == self.dep1.id for ni in dep1_instances)
        assert all(ni.deployment_id == dep2.id for ni in dep2_instances)

        assert len(dep1_n1_instances) == 2
        assert all(ni.deployment_id == self.dep1.id
                   for ni in dep1_n1_instances)
        assert all(ni.node_id == node1.id for ni in dep1_n1_instances)

        assert len(dep1_n2_instances) == 2
        assert all(ni.deployment_id == self.dep1.id
                   for ni in dep1_n2_instances)
        assert all(ni.node_id == node2.id for ni in dep1_n2_instances)

        assert len(dep2_n3_instances) == 2
        assert all(ni.deployment_id == dep2.id for ni in dep2_n3_instances)
        assert all(ni.node_id == node3.id for ni in dep2_n3_instances)

        assert len(dep2_n4_instances) == 2
        assert all(ni.deployment_id == dep2.id for ni in dep2_n4_instances)
        assert all(ni.node_id == node4.id for ni in dep2_n4_instances)

    def test_sort_node_instances_list(self):
        dep2 = self._deployment('d2')
        node1 = self._node('0', deployment=self.dep1)
        node2 = self._node('1', deployment=dep2)
        self._instance('00', node=node1)
        self._instance('11', node=node2)

        instances = self.client.node_instances.list(sort='node_id')
        assert len(instances) == 2
        assert instances[0].id == '00'
        assert instances[1].id == '11'

        instances = self.client.node_instances.list(
            sort='node_id', is_descending=True)
        assert len(instances) == 2
        assert instances[0].id == '11'
        assert instances[1].id == '00'

    def test_patch_before_put(self):
        """Updating a nonexistent node instance throws an error."""
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.node_instances.update(
                '1234',
                runtime_properties={'key': 'value'}
            )
        assert cm.exception.status_code == 404

    def test_node_actual_planned_instances(self):
        dep2 = self._deployment('dep2', scaling_groups={
            'group1': {
                'members': ['vm'],
                'properties': {'planned_instances': 2}
            }
        })
        numbers = {
            'number_of_instances': 2,
            'min_number_of_instances': 2,
            'max_number_of_instances': 2,
            'planned_number_of_instances': 2,
            'deploy_number_of_instances': 2,
        }
        self._node('vm', deployment=dep2, **numbers)
        node = self.client.nodes.get(dep2.id, 'vm')
        assert all(node[k] == v for k, v in numbers.items())

        # planned * group factor
        assert node['actual_planned_number_of_instances'] == 4

    def test_node_instance_update_system_properties(self):
        inst = self._instance('ni1')
        assert inst.system_properties is None
        self.client.node_instances.update(
            'ni1',
            system_properties={'property1': 'value1'},
            version=1,
        )
        assert inst.system_properties == {'property1': 'value1'}


class NodesCreateTest(base_test.BaseServerTestCase):
    def setUp(self):
        super().setUp()
        bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )
        self.dep1 = models.Deployment(
            id='dep1',
            blueprint=bp,
            creator=self.user,
            tenant=self.tenant,
        )

    def test_create_nodes(self):
        self.client.nodes.create_many('dep1', [
            {
                'id': 'test_node1',
                'type': 'cloudify.nodes.Root'
            },
            {
                'id': 'test_node2',
                'type': 'cloudify.nodes.Root'
            }
        ])
        nodes = self.sm.list(models.Node)
        node1 = [n for n in nodes if n.id == 'test_node1']
        node2 = [n for n in nodes if n.id == 'test_node2']
        assert len(node1) == 1
        node1 = node1[0]
        assert len(node2) == 1
        assert node1.deployment_id == 'dep1'

    def test_create_parameters(self):
        # those values don't necessarily make sense, but let's test that
        # all of them are passed through correctly
        node_type = 'node_type1'
        type_hierarchy = ['cloudify.nodes.Root', 'base_type', 'node_type1']
        relationships = [{
            'target_id': 'node1',
            'type': 'relationship_type1',
            'type_hierarchy': ['relationship_type1'],
            'properties': {'a': 'b'},
            'source_operations': {},
            'target_operations': {},
        }]
        properties = {'prop1': 'value'}
        operations = {'op1': 'operation'}
        current_instances = 3
        default_instances = 3
        min_instances = 2
        max_instances = 5
        plugins = ['plug1']
        self.client.nodes.create_many('dep1', [
            {
                'id': 'test_node1',
                'type': node_type,
                'type_hierarchy': type_hierarchy,
                'properties': properties,
                'relationships': relationships,
                'operations': operations,
                'plugins': plugins,
                'capabilities': {
                    'scalable': {
                        'properties': {
                            'current_instances': current_instances,
                            'default_instances': default_instances,
                            'min_instances': min_instances,
                            'max_instances': max_instances,
                        }
                    }
                }
            }
        ])
        deployment = self.sm.get(models.Deployment, 'dep1')
        node = self.sm.get(models.Node, 'test_node1')
        assert node.deployment == deployment
        assert node.type_hierarchy == type_hierarchy
        assert node.type == node_type
        assert node.properties == properties
        assert node.relationships == relationships
        assert node.plugins == plugins
        assert node.operations == operations
        assert node.number_of_instances == current_instances
        assert node.planned_number_of_instances == current_instances
        assert node.deploy_number_of_instances == default_instances
        assert node.min_number_of_instances == min_instances
        assert node.max_number_of_instances == max_instances

    def test_empty_list(self):
        self.client.nodes.create_many('dep1', [])  # doesn't throw


class NodeInstancesCreateTest(_NodeSetupMixin, base_test.BaseServerTestCase):
    def test_empty_list(self):
        self.client.node_instances.create_many('d1', [])  # doesn't throw

    def test_create_instances(self):
        self.client.nodes.create_many('d1', [
            {
                'id': 'test_node1',
                'type': 'cloudify.nodes.Root'
            }
        ])
        self.client.node_instances.create_many('d1', [
            {
                'id': 'test_node1_xyz123',
                'node_id': 'test_node1'
            }
        ])
        node = self.sm.get(models.Node, 'test_node1')
        node_instance = self.sm.get(models.NodeInstance, 'test_node1_xyz123')
        assert node_instance.node == node

    def test_instance_index(self):
        self.client.nodes.create_many('d1', [
            {
                'id': 'test_node1',
                'type': 'cloudify.nodes.Root'
            },
            {
                'id': 'test_node2',
                'type': 'cloudify.nodes.Root'
            },
        ])
        self.client.node_instances.create_many('d1', [
            {
                'id': 'test_node1_1',
                'node_id': 'test_node1'
            }
        ])
        instance1 = self.sm.get(models.NodeInstance, 'test_node1_1')
        self.client.node_instances.create_many('d1', [
            {
                'id': 'test_node1_2',
                'node_id': 'test_node1'
            },
            {
                'id': 'test_node2_1',
                'node_id': 'test_node2'
            },
        ])
        instance2 = self.sm.get(models.NodeInstance, 'test_node1_2')
        node2_instance1 = self.sm.get(models.NodeInstance, 'test_node2_1')
        assert instance1.index == 1
        assert instance2.index == 2
        assert node2_instance1.index == 1


@mock.patch('manager_rest.rest.rest_decorators.is_deployment_update')
class NodeInstancesDeleteTest(_NodeSetupMixin, base_test.BaseServerTestCase):
    def test_delete_instance(self, is_update_mock):
        is_update_mock.return_value = True

        node = self._node('node1')
        ni = models.NodeInstance(
            id='ni1_1',
            node=node,
            state='started',
            creator=self.user,
            tenant=self.tenant,
        )
        self.client.node_instances.delete(ni.id)

    def test_delete_not_in_dep_update(self, is_update_mock):
        is_update_mock.return_value = False

        node = self._node('node1')
        ni = models.NodeInstance(
            id='ni1_1',
            node=node,
            state='started',
            creator=self.user,
            tenant=self.tenant,
        )
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.node_instances.delete(ni.id)
        assert cm.exception.status_code == 403

    def test_delete_nonexistent(self, is_update_mock):
        is_update_mock.return_value = True
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.node_instances.delete('nonexistent')
        assert cm.exception.status_code == 404

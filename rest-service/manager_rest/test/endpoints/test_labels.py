#########
# Copyright (c) 2020 Cloudify Platform Ltd. All rights reserved
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

import uuid

from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test import base_test
from manager_rest.constants import RESERVED_LABELS


class LabelsBaseTestCase(base_test.BaseServerTestCase):
    __test__ = False

    LABELS = [{'env': 'aws'}, {'arch': 'k8s'}]
    LABELS_2 = [{'env': 'gcp'}, {'arch': 'k8s'}]
    UPDATED_LABELS = [{'env': 'gcp'}, {'arch': 'k8s'}]
    UPDATED_UPPERCASE_LABELS = [{'Env': 'GCp'}, {'ArCh': 'K8s'}]
    UPPERCASE_LABELS = [{'EnV': 'aWs'}, {'aRcH': 'k8s'}]
    DUPLICATE_LABELS = [{'env': 'aws'}, {'env': 'aws'}]
    INVALID_LABELS_LIST = [{'env': 'aws', 'aRcH': 'k8s'}]

    def setUp(self, resource, put_resource_with_labels_cmd):
        super().setUp()
        self.resource = resource
        self.labels_client = getattr(self.client, f'{resource}_labels')
        self.put_resource_with_labels = put_resource_with_labels_cmd

    def update_resource_labels(self, resource_id, labels):
        if self.resource == 'deployments':
            return self.client.deployments.update_labels(resource_id, labels)
        elif self.resource == 'blueprints':
            return self.client.blueprints.update(resource_id,
                                                 {'labels': labels})
        else:
            raise Exception('Resource unknown')

    def test_resource_creation_success_with_labels(self):
        resource = self.put_resource_with_labels(self.LABELS)
        self.assert_resource_labels(resource.labels, self.LABELS)

    def test_uppercase_labels_to_lowercase(self):
        resource = self.put_resource_with_labels(self.UPPERCASE_LABELS)
        self.assert_resource_labels(resource.labels,
                                    [{'env': 'aWs'}, {'arch': 'k8s'}])

    def test_creation_success_with_special_labels(self):
        labels = [{'k.e-y': '&val\xf3e'}, {'key': ' va=l ue'},
                  {'ke_y': 'val=\\,u:e'}]
        resource = self.put_resource_with_labels(labels)
        self.assert_resource_labels(resource.labels, labels)

    def test_creation_success_with_normalized_label_value(self):
        # Testing that the value Ó is being normalized and lowercased
        labels = [{'key': '\u004f\u0301'}]
        resource = self.put_resource_with_labels(labels)
        self.assert_resource_labels(resource.labels, [{'key': '\u00d3'}])

    def test_update_resource_labels(self):
        resource = self.put_resource_with_labels(self.LABELS)
        updated_res = self.update_resource_labels(resource.id,
                                                  self.UPDATED_LABELS)
        self.assert_resource_labels(updated_res.labels, self.UPDATED_LABELS)

    def test_update_uppercase_resource_labels(self):
        resource = self.put_resource_with_labels(self.LABELS)
        updated_res = self.update_resource_labels(
            resource.id, self.UPDATED_UPPERCASE_LABELS)
        self.assert_resource_labels(updated_res.labels,
                                    [{'env': 'GCp'}, {'arch': 'K8s'}])

    def test_remove_resource_labels(self):
        resource = self.put_resource_with_labels(self.LABELS)
        self.assert_resource_labels(resource.labels, self.LABELS)
        updated_res = self.update_resource_labels(resource.id, [])
        self.assertEmpty(updated_res.labels)

    def test_creation_failure_with_invalid_label_key(self):
        err_label = [{'k ey': 'value'}]
        error_msg = '`k ey`.*illegal characters'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.put_resource_with_labels,
                               labels=err_label)

    def test_invalid_use_of_system_prefix_in_labels(self):
        error_msg = '400: .*reserved for internal use'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.put_resource_with_labels,
                               labels=[{'csys-blah': 'val1'}])

    def test_creation_failure_with_invalid_label_value(self):
        err_labels = [{'key': 'test\n'}, {'key': 'test\t'}, {'key': 't,es t"'}]
        error_msg = '{0}.*illegal characters'
        for err_label in err_labels:
            self.assertRaisesRegex(CloudifyClientError,
                                   error_msg.format(err_label['key']),
                                   self.put_resource_with_labels,
                                   resource_id='i{0}'.format(uuid.uuid4()),
                                   labels=[err_label])

    def test_creation_failure_with_invalid_labels_list(self):
        error_msg = 'Labels must be a list of 1-entry dictionaries'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.put_resource_with_labels,
                               labels=self.INVALID_LABELS_LIST)

    def test_creation_failure_with_duplicate_labels(self):
        error_msg = 'You cannot define the same label twice'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.put_resource_with_labels,
                               labels=self.DUPLICATE_LABELS)

    def test_update_failure_with_invalid_labels_list(self):
        resource = self.put_resource_with_labels(self.LABELS)
        error_msg = 'Labels must be a list of 1-entry dictionaries'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.update_resource_labels,
                               resource_id=resource.id,
                               labels=self.INVALID_LABELS_LIST)

    def test_update_failure_with_duplicate_labels(self):
        resource = self.put_resource_with_labels(self.LABELS)
        error_msg = 'You cannot define the same label twice'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.update_resource_labels,
                               resource_id=resource.id,
                               labels=self.DUPLICATE_LABELS)

    def test_list_resource_labels_keys(self):
        self.put_resource_with_labels(self.LABELS, resource_id='res1')
        self.put_resource_with_labels(self.LABELS_2, resource_id='res2')
        keys_list = self.labels_client.list_keys()
        self.assertEqual(set(keys_list.items), {'env', 'arch'})

    def test_list_resource_labels_key_values(self):
        self.put_resource_with_labels(self.LABELS, resource_id='res1')
        self.put_resource_with_labels(self.LABELS_2, resource_id='res2')
        env_values = self.labels_client.list_key_values('env')
        arch_values = self.labels_client.list_key_values('arch')
        self.assertEqual(set(env_values.items), {'aws', 'gcp'})
        self.assertEqual(arch_values.items, ['k8s'])

    def test_resource_labels_empty_labels(self):
        keys_list = self.labels_client.list_keys()
        self.assertEmpty(keys_list.items)

    def test_resource_labels_key_does_not_exist(self):
        not_exist = self.labels_client.list_key_values('env')
        self.assertEmpty(not_exist.items)

    def test_get_reserved_labels(self):
        reserved_labels = self.labels_client.get_reserved_labels_keys()
        self.assertEqual(reserved_labels.items, list(RESERVED_LABELS))


class DeploymentsLabelsTestCase(LabelsBaseTestCase):
    __test__ = True

    def setUp(self):
        super().setUp('deployments', self.put_deployment_with_labels)

    def test_deployment_creation_success_without_labels(self):
        _, _, _, deployment = self.put_deployment()
        self.assertEmpty(deployment.labels)

    def test_update_empty_deployments_labels(self):
        _, _, _, deployment = self.put_deployment()
        self.assertEqual(deployment.labels, [])
        updated_dep = self.client.deployments.update_labels(deployment.id,
                                                            self.LABELS)
        self.assert_resource_labels(updated_dep.labels, self.LABELS)

    def test_create_deployment_labels_from_blueprint(self):
        self.put_blueprint(blueprint_id='bp1',
                           blueprint_file_name='blueprint_with_labels_1.yaml')

        deployment = self.client.deployments.create(
            blueprint_id='bp1', deployment_id='dep1',
            labels=[{'key1': 'key1_val1'}, {'new_key': 'NEW_VALUe'}])
        self.create_deployment_environment(deployment)
        deployment = self.client.deployments.get(deployment.id)

        expected_dep_labels = [
            {'key1': 'key1_val1'}, {'key2': 'kEy2_vaL1'}, {'key2': 'va l:u,E'},
            {'key2': 'key2_val2'}, {'new_key': 'NEW_VALUe'}
        ]
        self.assert_resource_labels(deployment.labels, expected_dep_labels)

    def test_get_label_intrinsic_function(self):
        new_labels = [{'input_key': 'input_value'}, {'key1': 'key1_val3'},
                      {'key1': 'key1_val2'}, {'key2': 'key2_val2'},
                      {'key3': 'output_value'}]
        self.put_deployment(
            blueprint_file_name='blueprint_with_capabilities.yaml',
            deployment_id='dep1')
        deployment = self.put_deployment_with_labels(
            new_labels,
            blueprint_file_name='blueprint_with_get_label.yaml')

        capabilities = self.client.deployments.capabilities.get(deployment.id)[
            'capabilities']
        outputs = self.client.deployments.outputs.get(deployment.id)['outputs']
        node = self.client.nodes.get(deployment.id, 'node1',
                                     evaluate_functions=True)

        self.assertEqual(node.properties, {'prop1': ['key2_val1', 'key2_val2'],
                                           'prop2': 'key1_val1'})
        self.assertEqual(capabilities,
                         {'cap1': 'key1_val2', 'cap2': ['input_value']})
        self.assertEqual(outputs, {'output1': 'default_value',
                                   'output2': 'output_value'})
        return deployment

    def test_get_label_not_exist_fails(self):
        self.put_deployment(
            deployment_id='dep1',
            blueprint_file_name='blueprint_with_get_label_not_exist.yaml')
        self.assertRaisesRegex(CloudifyClientError,
                               'does not have a label',
                               self.client.deployments.outputs.get,
                               deployment_id='dep1')

    def test_get_label_index_out_of_range_fails(self):
        self.put_deployment(
            deployment_id='dep1',
            blueprint_file_name='blueprint_with_get_label_index_out_of_'
                                'range.yaml')
        self.assertRaisesRegex(CloudifyClientError,
                               'index is out of range',
                               self.client.deployments.outputs.get,
                               deployment_id='dep1')


class BlueprintsLabelsTestCase(LabelsBaseTestCase):
    __test__ = True

    def setUp(self):
        super().setUp('blueprints', self.put_blueprint_with_labels)

    def test_blueprint_creation_success_without_labels(self):
        blueprint = self.put_blueprint()
        self.assertEmpty(blueprint.labels)

    def test_update_empty_blueprint_labels(self):
        blueprint = self.put_blueprint_with_labels(self.LABELS)
        updated_bp = self.client.blueprints.update(blueprint.id,
                                                   {'labels': []})
        self.assert_resource_labels(updated_bp.labels, [])

    def test_create_blueprint_labels_from_blueprint(self):
        blueprint = self.put_blueprint(
            blueprint_id='bp1',
            blueprint_file_name='blueprint_with_labels_1.yaml',
            labels=[{'bp_KEY1': 'bp_key1_val1'},
                    {'bp_key2': 'bp_key2_val1'},
                    {'new_bp_key': 'NEW_BP_value'}])
        expected_bp_labels = [
            {'bp_key1': 'BP_key1_val1'}, {'bp_key1': 'bp_key1_val1'},
            {'bp_key2': 'bp_key2_val1'}, {'bp_key2': 'bp_key2_val2'},
            {'new_bp_key': 'NEW_BP_value'}
        ]
        self.assert_resource_labels(blueprint.labels, expected_bp_labels)

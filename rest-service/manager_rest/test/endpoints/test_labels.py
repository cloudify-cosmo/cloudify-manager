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

from manager_rest.test import base_test
from manager_rest.test.attribute import attr


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class DeploymentsLabelsTestCase(base_test.BaseServerTestCase):

    LABELS = [{'env': 'aws'}, {'arch': 'k8s'}]
    LABELS_2 = [{'env': 'gcp'}, {'arch': 'k8s'}]

    def test_list_deployment_labels_keys(self):
        self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        keys_list = self.client.deployments_labels.list_keys()
        self.assertEqual(set(keys_list.items), {'env', 'arch'})

    def test_list_deployment_labels_key_values(self):
        self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        env_values = self.client.deployments_labels.list_key_values('env')
        arch_values = self.client.deployments_labels.list_key_values('arch')
        self.assertEqual(set(env_values.items), {'aws', 'gcp'})
        self.assertEqual(arch_values.items, ['k8s'])

    def test_deployment_labels_empty_labels(self):
        keys_list = self.client.deployments_labels.list_keys()
        self.assertEmpty(keys_list.items)

    def test_deployment_labels_key_does_not_exist(self):
        not_exist = self.client.deployments_labels.list_key_values('env')
        self.assertEmpty(not_exist.items)

    def test_list_blueprint_labels_keys(self):
        self.put_blueprint(blueprint_file_name='blueprint_with_labels_1.yaml')
        keys_list = self.client.blueprints_labels.list_keys()
        self.assertEqual(set(keys_list.items), {'bp_key1', 'bp_key2'})

    def test_list_blueprint_labels_key_values(self):
        self.put_blueprint(blueprint_file_name='blueprint_with_labels_1.yaml')
        key1_values = self.client.blueprints_labels.list_key_values('bp_key1')
        key2_values = self.client.blueprints_labels.list_key_values('bp_key2')
        self.assertEqual(set(key1_values.items), {'bp_key1_val1'})
        self.assertEqual(set(key2_values.items),
                         {'bp_key2_val1', 'bp_key2_val2'})

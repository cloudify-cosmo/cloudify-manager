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
from manager_rest.constants import CFY_LABELS


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class LabelsTestCase(base_test.BaseServerTestCase):
    LABELS = [{'env': 'aws'}, {'arch': 'k8s'}]
    LABELS_2 = [{'env': 'gcp'}, {'arch': 'k8s'}]

    def setUp(self, labels_client):
        super().setUp()
        self.labels_client = labels_client

    def _test_list_resource_labels_keys(self):
        keys_list = self.labels_client.list_keys()
        self.assertEqual(set(keys_list.items), {'env', 'arch'})

    def _test_list_resource_labels_key_values(self):
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
        self.assertEqual(reserved_labels.items, list(CFY_LABELS))


class DeploymentsLabelsTestCase(LabelsTestCase):
    def setUp(self):
        super().setUp(self.client.deployments_labels)

    def test_list_deployment_labels_keys(self):
        self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        self._test_list_resource_labels_keys()

    def test_list_deployment_labels_key_values(self):
        self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        self._test_list_resource_labels_key_values()


class BlueprintsLabelsTestCase(LabelsTestCase):
    def setUp(self):
        super().setUp(self.client.blueprints_labels)

    def test_list_blueprint_labels_keys(self):
        self.put_blueprint_with_labels(self.LABELS, blueprint_id='bp1')
        self.put_blueprint_with_labels(self.LABELS_2, blueprint_id='bp2')
        self._test_list_resource_labels_keys()

    def test_list_blueprint_labels_key_values(self):
        self.put_blueprint_with_labels(self.LABELS, blueprint_id='bp1')
        self.put_blueprint_with_labels(self.LABELS_2, blueprint_id='bp2')
        self._test_list_resource_labels_key_values()


# This way we avoid rom running this class too
del LabelsTestCase

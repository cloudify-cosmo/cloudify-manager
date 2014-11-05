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

import uuid

from base_test import BaseServerTestCase


class AttributesTestCase(BaseServerTestCase):

    def test_attributes(self):
        id_ = str(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='blueprint_for_get_attribute.yaml',
            blueprint_id=id_,
            deployment_id=id_)
        instances = self.client.node_instances.list(deployment_id=id_)

        node1 = [x for x in instances if x.node_id == 'node1'][0]
        node2 = [x for x in instances if x.node_id == 'node2'][0]
        node3 = [x for x in instances if x.node_id == 'node3'][0]
        node4 = [x for x in instances if x.node_id == 'node4'][0]

        self.client.node_instances.update(
            node1.id, runtime_properties={'key1': 'value1'})
        self.client.node_instances.update(
            node2.id, runtime_properties={'key2': 'value2'})
        self.client.node_instances.update(
            node3.id, runtime_properties={'key3': 'value3'})
        self.client.node_instances.update(
            node4.id, runtime_properties={'key4': 'value4'})

        deployment_id = id_
        context = {
            'self': node1.id,
            'source': node2.id,
            'target': node3.id
        }
        payload = {
            'node1': {'get_attribute': ['SELF', 'key1']},
            'node2': {'get_attribute': ['SOURCE', 'key2']},
            'node3': {'get_attribute': ['TARGET', 'key3']},
            'node4': {'get_attribute': ['node4', 'key4']},
        }
        expected_processed_payload = {
            'node1': 'value1',
            'node2': 'value2',
            'node3': 'value3',
            'node4': 'value4',
        }

        response = self.client.attributes.process(deployment_id,
                                                  context,
                                                  payload)
        self.assertEqual(response.deployment_id, deployment_id)
        self.assertEqual(response.payload, expected_processed_payload)

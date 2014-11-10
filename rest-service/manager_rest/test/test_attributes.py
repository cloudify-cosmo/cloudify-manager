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

from cloudify_rest_client.exceptions import FunctionsEvaluationError

from base_test import BaseServerTestCase


class AttributesTestCase(BaseServerTestCase):

    def setUp(self):
        super(AttributesTestCase, self).setUp()
        self.id_ = str(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='blueprint_for_get_attribute.yaml',
            blueprint_id=self.id_,
            deployment_id=self.id_)

        instances = self.client.node_instances.list(deployment_id=self.id_)

        self.node1 = [x for x in instances if x.node_id == 'node1'][0]
        self.node2 = [x for x in instances if x.node_id == 'node2'][0]
        self.node3 = [x for x in instances if x.node_id == 'node3'][0]
        self.node4 = [x for x in instances if x.node_id == 'node4'][0]

        self.client.node_instances.update(
            self.node1.id, runtime_properties={'key1': 'value1'})
        self.client.node_instances.update(
            self.node2.id, runtime_properties={'key2': 'value2'})
        self.client.node_instances.update(
            self.node3.id, runtime_properties={'key3': 'value3'})
        self.client.node_instances.update(
            self.node4.id, runtime_properties={'key4': 'value4'})

    def test_attributes(self):

        context = {
            'self': self.node1.id,
            'source': self.node2.id,
            'target': self.node3.id
        }
        payload = {
            'node1': {'get_attribute': ['SELF', 'key1']},
            'node2': {'get_attribute': ['SOURCE', 'key2']},
            'node3': {'get_attribute': ['TARGET', 'key3']},
            'node4': {'get_attribute': ['node4', 'key4']},
            'node6': {'get_attribute': ['node6', 'key6']}
        }
        expected_processed_payload = {
            'node1': 'value1',
            'node2': 'value2',
            'node3': 'value3',
            'node4': 'value4',
            'node6': 'value6',
        }

        response = self.client.evaluate.functions(self.id_,
                                                  context,
                                                  payload)
        self.assertEqual(response.deployment_id, self.id_)
        self.assertEqual(response.payload, expected_processed_payload)

    def test_missing_self(self):
        payload = {
            'node1': {'get_attribute': ['SELF', 'key1']},
        }
        try:
            self.client.evaluate.functions(self.id_, {}, payload)
            self.fail()
        except FunctionsEvaluationError as e:
            self.assertIn('SELF is missing', e.message)

    def test_missing_source(self):
        payload = {
            'node2': {'get_attribute': ['SOURCE', 'key2']},
        }
        try:
            self.client.evaluate.functions(self.id_, {}, payload)
            self.fail()
        except FunctionsEvaluationError as e:
            self.assertIn('SOURCE is missing', e.message)

    def test_missing_target(self):
        payload = {
            'node3': {'get_attribute': ['TARGET', 'key3']},
        }
        try:
            self.client.evaluate.functions(self.id_, {}, payload)
            self.fail()
        except FunctionsEvaluationError as e:
            self.assertIn('TARGET is missing', e.message)

    def test_multi_instance(self):
        payload = {
            'node5': {'get_attribute': ['node5', 'key5']},
        }
        try:
            self.client.evaluate.functions(self.id_, {}, payload)
            self.fail()
        except FunctionsEvaluationError as e:
            self.assertIn('Multi instances of node', e.message)

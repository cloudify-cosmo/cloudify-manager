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

from manager_rest.test import base_test
from cloudify_rest_client.exceptions import FunctionsEvaluationError


class AttributesTestCase(base_test.BaseServerTestCase):

    def setUp(self):
        super(AttributesTestCase, self).setUp()
        self.id_ = 'i{0}'.format(uuid.uuid4())
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
        with self.assertRaisesRegex(
                FunctionsEvaluationError, 'SELF is missing'):
            self.client.evaluate.functions(self.id_, {}, payload)

    def test_missing_source(self):
        payload = {
            'node2': {'get_attribute': ['SOURCE', 'key2']},
        }
        with self.assertRaisesRegex(
                FunctionsEvaluationError, 'SOURCE is missing'):
            self.client.evaluate.functions(self.id_, {}, payload)

    def test_missing_target(self):
        payload = {
            'node3': {'get_attribute': ['TARGET', 'key3']},
        }
        with self.assertRaisesRegex(
                FunctionsEvaluationError, 'TARGET is missing') as cm:
            self.client.evaluate.functions(self.id_, {}, payload)

        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.error_code, 'functions_evaluation_error')

    def test_ambiguous_multi_instance(self):
        payload = {
            'node5': {'get_attribute': ['node5', 'key5']},
        }
        with self.assertRaisesRegex(FunctionsEvaluationError, 'unambiguously'):
            self.client.evaluate.functions(self.id_, {}, payload)


class MultiInstanceAttributesTestCase(base_test.BaseServerTestCase):
    def test_multi_instance_attributes(self):
        # The actual multi instance resolution logic is tested in the dsl
        # parser unit tests. This test serves only to have an end to end path
        # that includes actual storage DeploymentNode and
        # DeploymentNodeInstance when using the intrinsic functions storage
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='get_attribute_multi_instance.yaml',
            blueprint_id=id_,
            deployment_id=id_)
        instances = self.client.node_instances.list(deployment_id=id_)
        node3_ids = [x.id for x in instances if x.node_id == 'node3']
        node6_ids = [x.id for x in instances if x.node_id == 'node6']
        for node3_id in node3_ids:
            self.client.node_instances.update(
                node3_id, runtime_properties={'key': node3_id})
        payload = {'node3': {'get_attribute': ['node3', 'key']}}
        contexts = [{'self': node6_id} for node6_id in node6_ids]
        expected_payloads = [{'node3': node3_id} for node3_id in node3_ids]
        result_payloads = [
            self.client.evaluate.functions(id_, contexts[i], payload).payload
            for i in range(2)]
        self.assertTrue((expected_payloads[0] == result_payloads[0] and
                         expected_payloads[1] == result_payloads[1]) or
                        (expected_payloads[0] == result_payloads[1] and
                         expected_payloads[1] == result_payloads[0]))

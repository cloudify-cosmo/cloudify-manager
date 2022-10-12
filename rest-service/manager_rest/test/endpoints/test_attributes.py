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

from manager_rest.storage import models
from manager_rest.test import base_test
from manager_rest.test.utils import node_intance_counts
from cloudify_rest_client.exceptions import FunctionsEvaluationError


class AttributesTestCase(base_test.BaseServerTestCase):

    def setUp(self):
        super(AttributesTestCase, self).setUp()
        self.id_ = 'i{0}'.format(uuid.uuid4())
        bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )
        dep = models.Deployment(
            id='dep1',
            blueprint=bp,
            creator=self.user,
            tenant=self.tenant,
        )
        self.id_ = dep.id

        for node_id, properties, runtime_properties, instance_count in [
            ('node1', {}, {'key1': 'value1'}, 1),
            ('node2', {}, {'key2': 'value2'}, 1),
            ('node3', {}, {'key3': 'value3'}, 1),
            ('node4', {}, {'key4': 'value4'}, 1),
            ('node5', {}, {}, 2),
            ('node6', {'key6': 'value6'}, {}, 1),
        ]:
            node = models.Node(
                id=node_id,
                deployment=dep,
                type='node',
                properties=properties,
                creator=self.user,
                tenant=self.tenant,
                **node_intance_counts(instance_count),
            )
            for num in range(instance_count):
                models.NodeInstance(
                    id=f'{node_id}_{num}',
                    node=node,
                    state='started',
                    runtime_properties=runtime_properties,
                    creator=self.user,
                    tenant=self.tenant,
                )

    def test_attributes(self):
        context = {
            'self': 'node1_0',
            'source': 'node2_0',
            'target': 'node3_0',
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
                FunctionsEvaluationError, 'SELF has no instances'):
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
    def setUp(self):
        super().setUp()
        self.id_ = 'i{0}'.format(uuid.uuid4())
        bp = models.Blueprint(
            id=self.id_, creator=self.user, tenant=self.tenant)
        dep = models.Deployment(
            id=self.id_, blueprint=bp, creator=self.user, tenant=self.tenant)
        node1 = models.Node(
            id='node1',
            deployment=dep,
            type='node',
            creator=self.user,
            tenant=self.tenant,
            **node_intance_counts(2),
        )
        node2 = models.Node(
            id='node2',
            deployment=dep,
            type='node',
            creator=self.user,
            tenant=self.tenant,
            **node_intance_counts(2),
        )
        for num in range(1, 3):
            instance_id = f'{node1.id}_{num}'
            models.NodeInstance(
                id=instance_id,
                node=node1,
                state='started',
                runtime_properties={'key': instance_id},
                creator=self.user,
                tenant=self.tenant,
            )
        for num in range(1, 3):
            instance_id = f'{node2.id}_{num}'
            target_id = f'{node1.id}_{num}'
            models.NodeInstance(
                id=instance_id,
                node=node2,
                state='started',
                relationships=[{
                    'type': 'cloudify.relationships.contained_in',
                    'target_id': target_id,
                    'target_name': 'node1',
                }],
                creator=self.user,
                tenant=self.tenant,
            )

    def test_multi_instance_attributes(self):
        # The actual multi instance resolution logic is tested in the dsl
        # parser unit tests. This test serves only to have an end to end path
        # that includes actual storage DeploymentNode and
        # DeploymentNodeInstance when using the intrinsic functions storage
        payload = {'node1': {'get_attribute': ['node1', 'key']}}
        result1 = self.client.evaluate.functions(
            self.id_,
            {'self': 'node2_1'},
            payload,
        ).payload
        result2 = self.client.evaluate.functions(
            self.id_,
            {'self': 'node2_2'},
            payload,
        ).payload
        assert result1 == {'node1': 'node1_1'}
        assert result2 == {'node1': 'node1_2'}

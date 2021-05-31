########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_dsl


@pytest.mark.usefixtures('mock_workflows_plugin')
@pytest.mark.usefixtures('testmockoperations_plugin')
class OperationMappingTest(AgentlessTestCase):

    def test_operation_mapping(self):
        dsl_path = resource("dsl/operation_mapping.yaml")
        deployment, _ = self.deploy_and_execute_workflow(dsl_path, 'workflow1')
        invocations = self.get_runtime_property(deployment.id,
                                                'mock_operation_invocation')[0]
        self.assertEqual(3, len(invocations))
        for invocation in invocations:
            self.assertEqual(1, len(invocation))
            self.assertEqual(invocation['test_key'], 'test_value')

    def test_operation_mapping_override(self):
        dsl_path = resource("dsl/operation_mapping.yaml")
        deployment, _ = self.deploy_and_execute_workflow(dsl_path, 'workflow2')
        invocations = self.get_runtime_property(deployment.id,
                                                'mock_operation_invocation')[0]
        self.assertEqual(3, len(invocations))
        for invocation in invocations:
            self.assertEqual(1, len(invocation))
            self.assertEqual(invocation['test_key'], 'overridden_test_value')

    def test_operation_mapping_undeclared_override(self):
        dsl_path = resource("dsl/operation_mapping.yaml")
        self.deploy_and_execute_workflow(dsl_path, 'workflow3')

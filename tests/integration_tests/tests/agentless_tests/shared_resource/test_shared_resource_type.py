# Copyright (c) 2019-2020 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
from integration_tests import AgentlessTestCase

pytestmark = pytest.mark.group_service_composition


class TestSharedResourceType(AgentlessTestCase):
    def setUp(self):
        super(TestSharedResourceType, self).setUp()
        test_blueprint = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
  - cloudify/types/types.yaml

node_templates:

  shared_resource_node:
    type: cloudify.nodes.SharedResource
    properties:
      resource_config:
        deployment:
            id: test
"""
        self.test_blueprint_path = self.make_yaml_file(test_blueprint)
        self.deployment_id = 'test'

    def _create_shared_resource_deployment(self):
        blueprint = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
  - cloudify/types/types.yaml

capabilities:
    test:
        value: 1
"""
        blueprint_path = self.make_yaml_file(blueprint)
        self.deploy(blueprint_path, deployment_id=self.deployment_id)

    def _validate_shared_resource_capabilities(self,
                                               deployment_id,
                                               capabilities):
        shared_resource_id = self.client.node_instances.list(
            deployment_id=deployment_id)[0].id
        runtime_props = self.client.node_instances.get(
            shared_resource_id).runtime_properties
        self.assertEqual(capabilities,
                         runtime_props['capabilities'])

    def test_connecting_to_live_deployment(self):
        self._create_shared_resource_deployment()

        deployment_id = 'root_dep'
        self.deploy_application(self.test_blueprint_path,
                                deployment_id=deployment_id)
        self._validate_shared_resource_capabilities(deployment_id,
                                                    {'test': 1})

    def test_connecting_to_not_existing_deployment(self):
        self.assertRaises(RuntimeError, self.deploy_application,
                          self.test_blueprint_path,
                          deployment_id='root_dep')

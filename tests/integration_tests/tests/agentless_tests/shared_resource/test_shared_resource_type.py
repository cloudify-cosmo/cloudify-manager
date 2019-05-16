# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

import uuid

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource


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

    def _create_shared_resource_deployment(self):
        blueprint_path = get_resource('dsl/basic.yaml')
        self.deploy(blueprint_path, deployment_id='test')

    def test_connecting_to_live_deployment(self):
        self._create_shared_resource_deployment()

        deployment_id = 'd{0}'.format(uuid.uuid4())
        self.deploy_application(self.test_blueprint_path,
                                deployment_id=deployment_id)

    def test_connecting_to_not_existing_deployment(self):
        deployment_id = 'd{0}'.format(uuid.uuid4())
        self.assertRaises(RuntimeError, self.deploy_application,
                          self.test_blueprint_path,
                          deployment_id=deployment_id)

########
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
from integration_tests.tests.utils import get_resource as resource


class ComponentTypeTest(AgentlessTestCase):
    def test_component_creation_with_blueprint_id(self):
        # install and uninstall
        basic_blueprint_path = \
            resource('dsl/basic.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='basic')
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource(
            'dsl/component_with_blueprint_id.yaml')
        self.deploy_application(dsl_path, deployment_id=deployment_id)
        self.assertTrue(self.client.deployments.get('basic'))
        self.undeploy_application(deployment_id)
        self.assertFalse(self.client.deployments.get('basic'))

    def test_component_creation_with_blueprint_package(self):
        # install and uninstall
        pass

    def test_component_creation_with_not_existing_blueprint_id(self):
        pass

    def test_component_creation_with_not_existing_blueprint_package(self):
        pass

########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import uuid
import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_general


@pytest.mark.usefixtures('testmockoperations_plugin')
class RetrieveResourceRenderingTest(AgentlessTestCase):
    dsl_path = resource('dsl/test-retrieve-resource-template.yaml')
    template_path = 'jinja_rendering/for_template_rendering_tests.conf'
    rendered_template_path = \
        resource('dsl/jinja_rendering/rendered_template.conf')

    def _get_expected_template(self):
        with open(self.rendered_template_path, 'r') as f:
            return f.read()

    def _retrieve_resource_test(self, mode):
        blueprint_id = 'blueprint-' + str(uuid.uuid4())
        deployment, _ = self.deploy_application(
            self.dsl_path,
            blueprint_id=blueprint_id,
            timeout_seconds=15,
            inputs={
                'rendering_tests_demo_conf': self.template_path,
                'mode': mode
            }
        )
        rendered_resource = self.get_runtime_property(deployment.id,
                                                      'rendered_resource')[0]
        expected = self._get_expected_template()
        return expected, rendered_resource

    def test_get_resource_template(self):
        expected, rendered_resource = self._retrieve_resource_test('get')
        self.assertEqual(expected, rendered_resource)

    def test_download_resource_template(self):
        expected, rendered_resource_path = \
            self._retrieve_resource_test('download')
        out = self.env.read_manager_file(rendered_resource_path)
        self.assertEqual(expected, out)

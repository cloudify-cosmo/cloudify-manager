########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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


from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import execute_workflow


class TestScriptMapping(TestCase):

    def test_script_mapping(self):
        """
        Tests policy/trigger/group creation and processing flow
        """
        dsl_path = resource('dsl/test_script_mapping.yaml')
        deployment, _ = deploy(dsl_path)
        execute_workflow('workflow', deployment.id)

        data = self.get_plugin_data(plugin_name='script_runner',
                                    deployment_id=deployment.id)
        self.assertEqual(data['op1_called_with_property'], 'op2_called')
        self.assertEqual(data['op2_prop'], 'op2_value')

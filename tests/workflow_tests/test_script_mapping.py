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


import os
import shutil

import testenv
from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import execute_workflow


class TestScriptMapping(TestCase):

    def test_script_mapping(self):
        dsl_path = resource('dsl/test_script_mapping.yaml')
        deployment, _ = deploy(dsl_path)
        execute_workflow('workflow', deployment.id)

        data = self.get_plugin_data(plugin_name='script',
                                    deployment_id=deployment.id)
        self.assertEqual(data['op1_called_with_property'], 'op2_called')
        self.assertEqual(data['op2_prop'], 'op2_value')

    def test_script_mapping_to_deployment_resource(self):
        dsl_path = resource('dsl/test_script_mapping.yaml')
        deployment, _ = deploy(dsl_path)

        workflow_script_path = resource('dsl/scripts/workflows/workflow.py')
        with open(workflow_script_path, 'r') as f:
            workflow_script_content = f.read()

        deployment_folder_on_fs = os.path.join(
                testenv.testenv_instance.fileserver_dir,
                'deployments/{0}/scripts/workflows'.format(deployment.id))
        try:
            os.makedirs(deployment_folder_on_fs)
            deployment_workflow_script_path = os.path.join(
                    deployment_folder_on_fs, 'workflow.py')
            self.logger.info('Writing workflow.py to: {0}'.format(
                    deployment_workflow_script_path))
            with open(deployment_workflow_script_path, 'w') as f:
                f.write(workflow_script_content)
                f.write(os.linesep)
                f.write("instance.execute_operation('test.op3')")
                f.write(os.linesep)

            execute_workflow('workflow', deployment.id)

            data = self.get_plugin_data(plugin_name='script',
                                        deployment_id=deployment.id)
            self.assertEqual(data['op1_called_with_property'], 'op2_called')
            self.assertEqual(data['op2_prop'], 'op2_value')
            self.assertIn('op3_called', data)

        finally:
            shutil.rmtree(deployment_folder_on_fs, ignore_errors=True)

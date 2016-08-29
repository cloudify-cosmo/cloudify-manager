########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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
from testenv.utils import undeploy_application as undeploy


class TestDeploymentLogs(TestCase):

    def test_deployment_logs(self):
        message = 'TEST MESSAGE'
        inputs = {'message': message}

        dsl_path = resource("dsl/deployment_logs.yaml")
        deployment, _ = deploy(dsl_path, inputs=inputs)

        deployment_log_path = ('/var/log/cloudify/mgmtworker/logs/{0}.log'
                               .format(deployment.id))

        def read_deployment_logs():
            return self.read_manager_file(deployment_log_path, no_strip=True)

        def verify_logs_exist_with_content():
            self.assertIn(message, read_deployment_logs())

        verify_logs_exist_with_content()

        undeploy(deployment.id, is_delete_deployment=True)

        # Verify log file id truncated on deployment delete
        self.assertEqual('', read_deployment_logs())

        deployment, _ = deploy(dsl_path, inputs=inputs,
                               deployment_id=deployment.id)

        # Verify new deployment with the same deployment id
        # can write to the previous location.
        verify_logs_exist_with_content()

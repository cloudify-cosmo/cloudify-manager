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

import pytest
import retrying

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_deployments


@pytest.mark.usefixtures('testmockoperations_plugin')
class TestDeploymentLogs(AgentlessTestCase):

    # retrying is needed as the delete_deployment_environment workflow
    # which truncates the deployment log file is async.
    @retrying.retry(wait_fixed=5000, stop_max_attempt_number=10)
    def _assert_log_file_truncated(self,
                                   read_deployment_logs_func,
                                   previous_log_file_size):
        self.assertLess(len(read_deployment_logs_func()),
                        previous_log_file_size)

    def test_deployment_logs(self):
        message = 'TEST MESSAGE'
        inputs = {'message': message}

        dsl_path = resource("dsl/deployment_logs.yaml")
        deployment, _ = self.deploy_application(dsl_path, inputs=inputs)

        deployment_log_path = ('/var/log/cloudify/mgmtworker/logs/{0}.log'
                               .format(deployment.id))

        def read_deployment_logs():
            return self.read_manager_file(deployment_log_path, no_strip=True)

        def verify_logs_exist_with_content():
            deployment_logs = read_deployment_logs()
            self.assertIn(message, deployment_logs)
            return len(deployment_logs)

        log_file_size = verify_logs_exist_with_content()

        self.undeploy_application(deployment.id, is_delete_deployment=True)

        # Verify log file id truncated on deployment delete
        self._assert_log_file_truncated(read_deployment_logs, log_file_size)

        deployment, _ = self.deploy_application(
                dsl_path, inputs=inputs,
                deployment_id=deployment.id)

        # Verify new deployment with the same deployment id
        # can write to the previous location.
        verify_logs_exist_with_content()

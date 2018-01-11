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

import time
import uuid

from cloudify_rest_client.executions import Execution

from integration_tests import AgentlessTestCase
from integration_tests.framework import postgresql
from integration_tests.tests.utils import (
    verify_deployment_environment_creation_complete,
    do_retries,
    get_resource as resource)


class ARIAExecutionsTest(AgentlessTestCase):

    def test_start_execution(self):
        execution, service = self._run_execution('install')
        pass

    def _run_execution(self, workflow_name):

        dsl_path = resource('dsl/aria//single-node.yaml')
        _id = uuid.uuid1()
        service_template_name = 'service_template_{0}'.format(_id)
        service_name = 'service_{0}'.format(_id)

        service_template = self.client.aria_service_templates.upload(
            dsl_path, service_template_name)
        service = self.client.aria_services.create(
            service_template.id, service_name)
        execution = self.client.aria_executions.start(service.id, workflow_name)

        return execution, service

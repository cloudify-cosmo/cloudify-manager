#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.
import os
from nose.plugins.attrib import attr

from manager_rest.test import base_test
from cloudify_rest_client.exceptions import CloudifyClientError

from . import common


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class ARIAExecutionsTestCase(base_test.BaseServerTestCase):

    def test_get_empty(self):
        result = self.client.aria_executions.list()
        self.assertEquals(0, len(result))

    def test_get_nonexistent_execution(self):
        try:
            self.client.aria_executions.get('15')
        except CloudifyClientError, e:
            self.assertEqual(404, e.status_code)

    def test_start_execution(self):
        common.create_service(
            self.client,
            os.path.join('hello-world', 'hello-world.yaml'),
            'hello',
            'hello-service'
        )

        service = self.client.aria_services.list(name='hello-service')[0]

        self.client.aria_executions.start(service.id, 'install')

        executions = self.client.aria_executions.list(
            service_name='hello-service')
        self.assertEqual(1, len(executions))
        execution = executions[0]
        self.assertEqual(execution.service_name, 'hello-service')

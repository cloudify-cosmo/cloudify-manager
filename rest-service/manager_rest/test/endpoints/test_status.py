#########
# Copyright (c) 2014-2019 Cloudify Platform Ltd. All rights reserved
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

from cloudify.cluster_status import ServiceStatus

from manager_rest.test import base_test


class StatusTestCase(base_test.BaseServerTestCase):
    def test_get_status(self):
        result = self.client.manager.get_status()

        # There is no systemd in unit tests so the status response is FAIL
        self.assertEqual(result['status'], ServiceStatus.FAIL)
        self.assertEqual(type(result['services']), dict)

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

from flask_security import current_user


from manager_rest.test import base_test
from manager_rest.test.attribute import attr
from manager_rest.storage import management_models


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class StatusTestCase(base_test.BaseServerTestCase):

    def test_get_status(self):
        self._assert_last_logic_time_value(None)
        result = self.client.manager.get_status()
        self.assertEqual(result['status'], 'running')
        self.assertEqual(type(result['services']), list)
        self._assert_last_logic_time_value(None)

    def _assert_last_logic_time_value(self, value):
        login_time_before = self.sm.get(management_models.User,
                                        current_user.id).last_login_at
        self.assertEqual(login_time_before, value)

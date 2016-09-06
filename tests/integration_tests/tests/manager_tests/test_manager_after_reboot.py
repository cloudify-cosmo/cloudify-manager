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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from integration_tests import ManagerTestCase


class ManagerAfterRebootTest(ManagerTestCase):

    def test_manager_after_reboot(self):
        self.run_manager()
        context_before = self.client.manager.get_context()
        self.restart_manager()
        context_after = self.client.manager.get_context()
        self.assertEqual(context_before, context_after)
        self.test_hello_world()

#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

import yaml
import tempfile

from integration_tests import AgentlessTestCase
from integration_tests.framework.constants import AUTHORIZATION_FILE_LOCATION


class ManagerConfigTestCase(AgentlessTestCase):
    def test_reload_config(self):
        new_permission = 'test_reload'
        new_config = {new_permission: new_permission}
        self._change_authorization_config(new_config)

        # The new permission is not updated yet
        manager_config = self.client.manager_config.get()
        permissions = manager_config['authorization']['permissions']
        self.assertEquals(permissions.get(new_permission, None), None)

        self.client.manager_config.reload()

        # The new permission is updated
        manager_config = self.client.manager_config.get()
        permissions = manager_config['authorization']['permissions']
        self.assertEquals(permissions.get(new_permission, None),
                          new_permission)

    def _change_authorization_config(self, new_permissions_config):
        auth_config = yaml.load(self.read_manager_file(
            AUTHORIZATION_FILE_LOCATION))
        auth_config['permissions'].update(new_permissions_config)
        with tempfile.NamedTemporaryFile() as f:
            yaml.dump(auth_config, f)
            f.flush()
            self.copy_file_to_manager(source=f.name,
                                      target=AUTHORIZATION_FILE_LOCATION,
                                      owner='cfyuser')

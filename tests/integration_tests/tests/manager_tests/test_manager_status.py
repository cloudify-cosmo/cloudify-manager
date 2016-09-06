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

from integration_tests import ManagerTestCase


class ManagerStatusTest(ManagerTestCase):

    def test_manager_status(self):
        self.run_manager()
        self.status = self.client.manager.get_status()['services']
        self._test_pre_reboot()
        self._test_during_reboot()
        self._test_post_reboot()

    def _test_pre_reboot(self):
        stopped = self._get_stopped_services()
        self.assertEqual(stopped, [], 'stopped services: {0}'
                         .format(','.join(stopped)))

    def _test_during_reboot(self):
        pre_reboot_status = self.status
        self.restart_manager()
        post_reboot_status = self.client.manager.get_status()['services']
        self.assertEqual(len(pre_reboot_status), len(post_reboot_status),
                         "number of jobs before reboot isn\'t equal to \
                          number of jobs after reboot")
        zipped = zip(pre_reboot_status, post_reboot_status)
        for pre, post in zipped:
            self.assertEqual(pre.get('name'), post.get('name'),
                             'pre and post reboot status is not equal:'
                             '{0}\n {1}'.format(pre.get('name'),
                                                post.get('name')))

    def _test_post_reboot(self):
        stopped = self._get_stopped_services()
        self.assertEqual(stopped, [], 'stopped services: {0}'
                         .format(','.join(stopped)))

    def _get_service_names(self):
        return [each['display_name'] for each in self.status]

    def _get_stopped_services(self):
        return [each['display_name'] for each in self.status
                if each and 'instances' not in each]

# ***************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# ***************************************************************************/
import unittest

__author__ = 'elip'


class TasksTest(unittest.TestCase):

    def test_add_module_paths_to_includes(self):

        app_parameters = '--broker=amqp://guest:guest@127.0.0.1:5672// '\
                         '--include=plugin_installer.tasks --events ' \
                         '--app=cloudify -Q test-node-id -n test-node-id '\
                         '--logfile=C:\CloudifyAgent\celery.log ' \
                         '--pidfile=C:\CloudifyAgent\celery.pid'

        from windows_plugin_installer.tasks import add_module_paths_to_includes
        new_app_parameters = add_module_paths_to_includes('mock_plugin.tasks', app_parameters)

        expected_app_parameters = '--broker=amqp://guest:guest@127.0.0.1:5672// '\
                                  '--include=plugin_installer.tasks,mock_plugin.tasks --events '\
                                  '--app=cloudify -Q test-node-id -n test-node-id '\
                                  '--logfile=C:\CloudifyAgent\celery.log '\
                                  '--pidfile=C:\CloudifyAgent\celery.pid'

        self.assertEqual(new_app_parameters, expected_app_parameters)
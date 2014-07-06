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

__author__ = 'elip'

import unittest
import os

from cloudify.constants import LOCAL_IP_KEY


class PluginUtilsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ[LOCAL_IP_KEY] = 'localhost'

    def test_extract_plugin_name_from_remote_url(self):

        from windows_plugin_installer.plugin_utils import extract_plugin_name

        plugin_url = 'https://github.com/cloudify-cosmo/' \
                     'cloudify-bash-plugin/archive/develop.zip'
        self.assertEqual(
            'cloudify-bash-plugin',
            extract_plugin_name(plugin_url))

    def test_extract_plugin_name_from_local_folder(self):

        from windows_plugin_installer.plugin_utils import \
            extract_plugin_name
        from windows_plugin_installer.tests import \
            resources
        plugin_url = '{0}\mock-plugin'\
                     .format(os.path.dirname(resources.__file__))
        self.assertEqual('mock-plugin', extract_plugin_name(plugin_url))

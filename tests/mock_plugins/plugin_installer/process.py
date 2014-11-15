########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

import os
import shutil
from cloudify import ctx

from mock_plugins.plugin_installer import PluginInstaller


class ProcessBackedPluginInstaller(PluginInstaller):

    def install(self, plugin):

        source_plugin_path = os.path.join(
            os.environ['MOCK_PLUGINS_PATH'],
            plugin['source']
        )

        target_plugin_path = os.path.join(
            os.environ['ENV_DIR'],
            plugin['source']
        )

        if not os.path.exists(target_plugin_path):

            # just copy the plugin
            # directory to the
            # worker environment

            ctx.logger.info('Copying {0} --> {1}'
                            .format(source_plugin_path,
                                    target_plugin_path))

            shutil.copytree(
                src=source_plugin_path,
                dst=target_plugin_path,
                ignore=shutil.ignore_patterns('*.pyc')
            )


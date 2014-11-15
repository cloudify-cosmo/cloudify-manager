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

from cloudify import ctx
from cloudify.decorators import operation
from mock_plugins.plugin_installer.consumer import \
    ConsumerBackedPluginInstaller
from mock_plugins.plugin_installer.process import \
    ProcessBackedPluginInstaller

from testenv.utils import update_storage


@operation
def install(plugins, **kwargs):

    plugin_installer = get_backend()

    for plugin in plugins:
        with update_storage(ctx) as data:
            plugin_installer.install(plugin)
            plugin_name = plugin['name']
            data[ctx.task_target] = data.get(ctx.task_target, {})
            data[ctx.task_target][plugin_name] = \
                data[ctx.task_target].get(plugin_name, [])
            data[ctx.task_target][plugin_name].append('installed')


def get_backend():
    if os.environ.get('PROCESS_MODE'):
        return ProcessBackedPluginInstaller()
    return ConsumerBackedPluginInstaller()

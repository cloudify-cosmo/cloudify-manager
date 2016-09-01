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

from cloudify import ctx
from cloudify.decorators import operation

from integration_tests_plugins.cloudify_agent import consumer

from integration_tests_plugins.utils import update_storage


@operation
def install_plugins(plugins, **_):
    _operate_on_plugins(plugins, 'installed')


@operation
def uninstall_plugins(plugins, **_):
    _operate_on_plugins(plugins, 'uninstalled')


def _operate_on_plugins(plugins, new_state):
    plugin_installer = get_backend()
    func = plugin_installer.install if new_state == 'installed' \
        else plugin_installer.uninstall
    for plugin in plugins:
        with update_storage(ctx) as data:
            if (new_state == 'uninstalled' and
                    'raise_exception_on_delete' in data):
                raise Exception("Exception raised intentionally")
            func(plugin)
            plugin_name = plugin['name']
            task_target = ctx.task_target or 'local'
            data[task_target] = data.get(task_target, {})
            data[task_target][plugin_name] = \
                data[task_target].get(plugin_name, [])
            data[task_target][plugin_name].append(new_state)
        ctx.logger.info('Plugin {0} {1}'.format(plugin['name'], new_state))


def get_backend():
    return consumer.ConsumerBackedPluginInstaller()

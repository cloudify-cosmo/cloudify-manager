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

from cloudify.decorators import operation
from testenv.utils import update_storage


@operation
def install(ctx, plugins, **kwargs):

    for plugin in plugins:
        plugin_name = plugin['name']
        ctx.logger.info('Installing plugin {0}'.format(plugin_name))
        with update_storage(ctx) as data:
            data[ctx.task_target] = data.get(ctx.task_target, {})
            data[ctx.task_target][plugin_name] = data[ctx.task_target].get(plugin_name, [])
            data[ctx.task_target][plugin_name].append('installed')

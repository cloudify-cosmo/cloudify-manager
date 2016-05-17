########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

from cloudify.decorators import workflow


@workflow(system_wide=True)
def install(ctx, plugin, **_):
    return _operate_on_plugin(ctx, plugin, 'install')


@workflow(system_wide=True)
def uninstall(ctx, plugin, **_):
    return _operate_on_plugin(ctx, plugin, 'uninstall')


def _operate_on_plugin(ctx, plugin, action):
    graph = ctx.graph_mode()
    graph.add_task(ctx.execute_task(
        'cloudify_agent.operations.{0}_plugins'.format(action),
        kwargs={'plugins': [plugin]}))
    return graph.execute()

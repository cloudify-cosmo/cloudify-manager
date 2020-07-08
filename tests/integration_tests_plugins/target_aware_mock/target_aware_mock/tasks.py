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


@operation
def create(ctx, **kwargs):
    ctx.instance.runtime_properties['create'] = {'target': ctx.task_target}


@operation
def start(ctx, **kwargs):
    ctx.instance.runtime_properties['start'] = {'target': ctx.task_target}


@operation
def stop(ctx, **kwargs):
    ctx.instance.runtime_properties['stop'] = {'target': ctx.task_target}


@operation
def delete(ctx, **kwargs):
    ctx.instance.runtime_properties['delete'] = {'target': ctx.task_target}


@operation
def hook_task(context, **kwargs):
    with open('/tmp/hook_task.txt', 'a') as f:
        f.write("In hook_task of version 1.0, context: {0} kwargs: {1}"
                .format(context, kwargs))

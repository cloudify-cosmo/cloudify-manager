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


from time import time

from cloudify.decorators import operation


state = []


@operation
def configure_connection(ctx, **kwargs):
    append_to_state(ctx)


@operation
def unconfigure_connection(ctx, **kwargs):
    append_to_state(ctx)


def append_to_state(ctx):
    global state
    state.append({
        'id': ctx.node_id,
        'related_id': ctx.related.node_id,
        'time': time(),
        'properties': ctx.properties,
        'related_properties': ctx.related.properties,
        'capabilities': ctx.capabilities.get_all()
    })


@operation
def get_state(**kwargs):
    return state

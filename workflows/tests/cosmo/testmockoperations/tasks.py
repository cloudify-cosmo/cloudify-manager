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

from cosmo.events import set_reachable as reachable
from cosmo.events import set_unreachable as unreachable
from time import time
from cloudify.decorators import operation

state = []
touched_time = None
unreachable_call_order = []
mock_operation_invocation = []


@operation
def make_reachable(__cloudify_id, ctx, **kwargs):
    reachable(__cloudify_id)
    global state
    state.append({
        'id': __cloudify_id,
        'time': time(),
        'capabilities': ctx.capabilities.get_all()
    })


@operation
def make_unreachable(__cloudify_id, **kwargs):
    unreachable(__cloudify_id)
    global unreachable_call_order
    unreachable_call_order.append({
        'id': __cloudify_id,
        'time': time()
    })


@operation
def set_property(property_name, value, ctx, **kwargs):
    ctx[property_name] = value


@operation
def touch(**kwargs):
    global touched_time
    touched_time = time()


@operation
def get_state(**kwargs):
    return state


@operation
def get_touched_time(**kwargs):
    return touched_time


@operation
def is_unreachable_called(__cloudify_id, **kwargs):
    return next((x for x in
                 unreachable_call_order if x['id'] == __cloudify_id), None)


@operation
def get_unreachable_call_order(**kwargs):
    return unreachable_call_order


@operation
def mock_operation(__cloudify_id, ctx, mockprop, **kwargs):
    global mock_operation_invocation
    mock_operation_invocation.append({
        'id': __cloudify_id,
        'mockprop': mockprop,
        'kwargs': kwargs
    })


@operation
def get_mock_operation_invocations(**kwargs):
    return mock_operation_invocation

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
from cloudify.manager import get_manager_rest_client

state = []
touched_time = None
unreachable_call_order = []
mock_operation_invocation = []
node_states = []


@operation
def make_reachable(ctx, **kwargs):
    global state
    state_info = {
        'id': ctx.node_id,
        'time': time(),
        'capabilities': ctx.capabilities.get_all()
    }
    ctx.logger.info('Appending to state [node_id={0}, state={1}]'
                    .format(ctx.node_id, state_info))
    state.append(state_info)


@operation
def make_unreachable(ctx, **kwargs):
    global unreachable_call_order
    unreachable_call_order.append({
        'id': ctx.node_id,
        'time': time()
    })


@operation
def set_property(property_name, value, ctx, **kwargs):
    ctx.logger.info('Setting property [{0}={1}] for node: {2}'
                    .format(property_name, value, ctx.node_id))
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
def is_unreachable_called(node_id, **kwargs):
    return next((x for x in
                 unreachable_call_order if x['id'] == node_id), None)


@operation
def get_unreachable_call_order(**kwargs):
    return unreachable_call_order


@operation
def mock_operation(ctx, mockprop, **kwargs):
    global mock_operation_invocation
    mock_operation_invocation.append({
        'id': ctx.node_id,
        'mockprop': mockprop,
        'kwargs': kwargs
    })



@operation
def get_mock_operation_invocations(**kwargs):
    return mock_operation_invocation


@operation
def append_node_state(ctx, **kwargs):
    client = get_manager_rest_client()
    node_state = client.get_node_state(ctx.node_id,
                                       get_state=True,
                                       get_runtime_properties=False)
    global node_states
    node_states.append(node_state['state'])


@operation
def get_node_states(**kwargs):
    global node_states
    return node_states
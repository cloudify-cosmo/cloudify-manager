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
import tempfile
import os
import shutil
from cloudify.manager import get_manager_rest_client


state = []
touched_time = None
unreachable_call_order = []
mock_operation_invocation = []
node_states = []
get_resource_operation_invocation = []


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
    ctx.runtime_properties[property_name] = value


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
def get_resource_operation(ctx, resource_path, **kwargs):
    # trying to retrieve a resource
    res1 = ctx.download_resource(resource_path)
    if not res1:
        raise RuntimeError('Failed to get resource {0}'.format(resource_path))
    with open(res1, 'r') as f:
        res1_data = f.read()
    os.remove(res1)

    # trying to retrieve a resource to a specific location
    tempdir = tempfile.mkdtemp()
    try:
        filepath = os.path.join(tempdir, 'temp-resource-file')
        res2 = ctx.download_resource(resource_path, filepath)
        if not res2:
            raise RuntimeError('Failed to get resource {0} into {1}'.format(
                resource_path, filepath))
        with open(res2, 'r') as f:
            res2_data = f.read()
    finally:
        shutil.rmtree(tempdir)

    global get_resource_operation_invocation
    get_resource_operation_invocation.append({
        'res1_data': res1_data,
        'res2_data': res2_data,
        'custom_filepath': filepath,
        'res2_path': res2
    })


@operation
def get_resource_operation_invocations(**kwargs):
    return get_resource_operation_invocation


@operation
def get_mock_operation_invocations(**kwargs):
    return mock_operation_invocation


@operation
def append_node_state(ctx, **kwargs):
    client = get_manager_rest_client()
    node_state = client.get_node_instance(
        ctx.node_id,
        get_state_and_runtime_properties=True)
    global node_states
    node_states.append(node_state['state'])


@operation
def get_node_states(**kwargs):
    global node_states
    return node_states

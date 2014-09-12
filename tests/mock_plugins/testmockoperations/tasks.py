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

import time
import tempfile
import os
import shutil

from cloudify.manager import get_rest_client
from cloudify.manager import get_node_instance_ip
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from cloudify.exceptions import RecoverableError
from testenv.utils import update_storage


@operation
def make_reachable(ctx, **kwargs):
    state_info = {
        'id': ctx.node_id,
        'time': time.time(),
        'capabilities': ctx.capabilities.get_all()
    }
    ctx.logger.info('Appending to state [node_id={0}, state={1}]'
                    .format(ctx.node_id, state_info))
    with update_storage(ctx) as data:
        data['state'] = data.get('state', [])
        data['state'].append(state_info)


@operation
def make_unreachable(ctx, **kwargs):
    with update_storage(ctx) as data:
        data['unreachable_call_order'] = data.get('unreachable_call_order', [])
        data['unreachable_call_order'].append({
            'id': ctx.node_id,
            'time': time.time()
        })


@operation
def set_property(ctx, **kwargs):
    property_name = ctx.properties['property_name']
    value = ctx.properties['value']
    ctx.logger.info('Setting property [{0}={1}] for node: {2}'
                    .format(property_name, value, ctx.node_id))
    ctx.runtime_properties[property_name] = value


@operation
def del_property(ctx, **kwargs):
    property_name = ctx.properties['property_name']
    ctx.logger.info('Deleting property [{0}] for node: {1}'
                    .format(property_name, ctx.node_id))
    del(ctx.runtime_properties[property_name])


@operation
def touch(ctx, **kwargs):
    with update_storage(ctx) as data:
        data['touched_time'] = data.get('touched_time', None)
        data['touched_time'] = time.time()


@operation
def start_monitor(ctx, **kwargs):
    with update_storage(ctx) as data:
        data['monitoring_operations_invocation'] = data.get('monitoring_operations_invocation', [])
        data['monitoring_operations_invocation'].append({
            'id': ctx.node_id,
            'operation': 'start_monitor'
        })


@operation
def stop_monitor(ctx, **kwargs):
    with update_storage(ctx) as data:
        data['monitoring_operations_invocation'] = data.get('monitoring_operations_invocation', [])
        data['monitoring_operations_invocation'].append({
            'id': ctx.node_id,
            'operation': 'stop_monitor'
        })


@operation
def mock_operation(ctx, **kwargs):
    mockprop = get_prop('mockprop', ctx, kwargs)
    with update_storage(ctx) as data:
        data['mock_operation_invocation'] = data.get('mock_operation_invocation', [])
        data['mock_operation_invocation'].append({
            'id': ctx.node_id,
            'mockprop': mockprop,
            'properties': {key: value for (key, value) in ctx.properties.items()}
        })


@operation
def mock_operation_from_custom_workflow(ctx, key, value, **kwargs):
    with update_storage(ctx) as data:
        data['mock_operation_invocation'] = data.get('mock_operation_invocation', [])
        data['mock_operation_invocation'].append({
            key: value
        })


@operation
def mock_operation_get_instance_ip(ctx, **kwargs):
    with update_storage(ctx) as data:
        data['mock_operation_invocation'] = data.get('mock_operation_invocation', [])
        data['mock_operation_invocation'].append((
            ctx.node_name, get_node_instance_ip(ctx.node_id)
        ))

    return True


@operation
def mock_operation_get_instance_ip_from_context(ctx, **_):
    with update_storage(ctx) as data:
        data['mock_operation_invocation'] = data.get('mock_operation_invocation', [])
        data['mock_operation_invocation'].append((
            ctx.node_name, ctx.host_ip
        ))

    return True


@operation
def mock_operation_get_instance_ip_of_related_from_context(ctx, **_):
    with update_storage(ctx) as data:
        data['mock_operation_invocation'] = data.get('mock_operation_invocation', [])
        data['mock_operation_invocation'].append((
            '{}_rel'.format(ctx.node_name), ctx.related.host_ip
        ))

    return True


@operation
def get_resource_operation(ctx, **kwargs):
    resource_path = get_prop('resource_path', ctx, kwargs)
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

    with update_storage(ctx) as data:
        data['get_resource_operation_invocation'] = data.get('get_resource_operation_invocation', [])
        data['get_resource_operation_invocation'].append({
            'res1_data': res1_data,
            'res2_data': res2_data,
            'custom_filepath': filepath,
            'res2_path': res2
        })


@operation
def append_node_state(ctx, **kwargs):
    client = get_rest_client()
    instance = client.node_instances.get(ctx.node_id)
    with update_storage(ctx) as data:
        data['node_states'] = data.get('node_states', [])
        data['node_states'].append(instance.state)


@operation
def sleep(ctx, **kwargs):
    sleep_time = ctx.properties['sleep'] if 'sleep' in ctx.properties \
        else kwargs['sleep']
    time.sleep(int(sleep_time))


@operation
def fail(ctx, **kwargs):
    fail_count = get_prop('fail_count', ctx, kwargs, 1000000)

    with update_storage(ctx) as data:
        data['failure_invocation'] = data.get('failure_invocation', [])
        data['failure_invocation'].append(time.time())

    if len(data['failure_invocation']) > fail_count:
        return

    message = 'TEST_EXPECTED_FAIL'
    non_recoverable = get_prop('non_recoverable', ctx, kwargs, False)
    recoverable = get_prop('recoverable', ctx, kwargs, False)
    retry_after = get_prop('retry_after', ctx, kwargs)

    if non_recoverable:
        exception = NonRecoverableError(message)
    elif recoverable:
        exception = RecoverableError(message, retry_after=retry_after)
    else:
        exception = RuntimeError(message)

    raise exception


@operation
def host_get_state(ctx, **kwargs):
    with update_storage(ctx) as data:
        data['host_get_state_invocation'] = data.get('host_get_state_invocation', [])
        data['host_get_state_invocation'].append(time.time())

    if len(data['host_get_state_invocation']) <= get_prop('false_count',
                                                          ctx,
                                                          kwargs):
        return False
    return True


def get_prop(prop_name, ctx, kwargs, default=None):
    if prop_name in kwargs:
        return kwargs[prop_name]
    elif prop_name in ctx.properties:
        return ctx.properties[prop_name]
    else:
        return default

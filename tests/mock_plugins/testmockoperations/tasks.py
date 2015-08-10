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
        'id': ctx.instance.id,
        'time': time.time(),
        'capabilities': ctx.capabilities.get_all()
    }
    ctx.logger.info('Appending to state [node_id={0}, state={1}]'
                    .format(ctx.instance.id, state_info))
    with update_storage(ctx) as data:
        data['state'] = data.get('state', [])
        data['state'].append(state_info)


@operation
def make_unreachable(ctx, **kwargs):
    with update_storage(ctx) as data:
        data['unreachable_call_order'] = data.get('unreachable_call_order', [])
        data['unreachable_call_order'].append({
            'id': ctx.instance.id,
            'time': time.time()
        })


@operation
def set_property(ctx, **kwargs):
    property_name = ctx.node.properties['property_name']
    value = ctx.node.properties['value']
    ctx.logger.info('Setting property [{0}={1}] for node: {2}'
                    .format(property_name, value, ctx.instance.id))
    ctx.instance.runtime_properties[property_name] = value


@operation
def del_property(ctx, **kwargs):
    property_name = ctx.node.properties['property_name']
    ctx.logger.info('Deleting property [{0}] for node: {1}'
                    .format(property_name, ctx.instance.id))
    del(ctx.instance.runtime_properties[property_name])


@operation
def touch(ctx, **kwargs):
    with update_storage(ctx) as data:
        data['touched_time'] = data.get('touched_time', None)
        data['touched_time'] = time.time()


@operation
def start_monitor(ctx, **kwargs):
    with update_storage(ctx) as data:
        data['monitoring_operations_invocation'] = data.get(
            'monitoring_operations_invocation', []
        )
        data['monitoring_operations_invocation'].append({
            'id': ctx.instance.id,
            'operation': 'start_monitor'
        })


@operation
def stop_monitor(ctx, **kwargs):
    with update_storage(ctx) as data:
        data['monitoring_operations_invocation'] = data.get(
            'monitoring_operations_invocation', []
        )
        data['monitoring_operations_invocation'].append({
            'id': ctx.instance.id,
            'operation': 'stop_monitor'
        })


@operation
def mock_operation(ctx, **kwargs):
    mockprop = get_prop('mockprop', ctx, kwargs)
    with update_storage(ctx) as data:
        data['mock_operation_invocation'] = data.get(
            'mock_operation_invocation', []
        )
        data['mock_operation_invocation'].append({
            'id': ctx.instance.id,
            'mockprop': mockprop,
            'properties': {
                key: value for (key, value) in ctx.node.properties.items()
            }
        })


@operation
def mock_operation_from_custom_workflow(ctx, key, value, **kwargs):
    saving_multiple_params_op(ctx, {key: value}, **kwargs)


@operation
def saving_multiple_params_op(ctx, params, **_):
    with update_storage(ctx) as data:
        invocations = data['mock_operation_invocation'] = data.get(
            'mock_operation_invocation', []
        )
        invocations.append(params)


def saving_operation_info(ctx, op, main_node, second_node=None, **_):
    with update_storage(ctx) as data:
        invocations = data['mock_operation_invocation'] = data.get(
            'mock_operation_invocation', []
        )
        num = data.get('num', 0) + 1
        data['num'] = num

        op_info = {'operation': op, 'num': num}
        if second_node is None:
            op_info.update({
                'node': main_node.node.name,
                'id': main_node.instance.id,
                'target_ids': [r.target.instance.id
                               for r in main_node.instance.relationships]
            })
        else:
            op_info.update({
                'id': main_node.instance.id,
                'source': main_node.node.name,
                'target': second_node.node.name
            })
        invocations.append(op_info)

    client = get_rest_client()
    fail_input = client.deployments.get(ctx.deployment.id).inputs.get(
        'fail', [])
    fail_input = [i for i in fail_input if
                  i.get('workflow') == ctx.workflow_id and
                  i.get('node') == main_node.node.id and
                  i.get('operation') == ctx.operation.name]
    if fail_input:
        raise RuntimeError('TEST_EXPECTED_FAIL')


def saving_rel_operation_info(ctx, op, **kwargs):
    saving_operation_info(ctx, op, ctx.source, ctx.target,
                          **kwargs)


def saving_non_rel_operation_info(ctx, op, **kwargs):
    saving_operation_info(ctx, op, ctx, **kwargs)


@operation
def mock_lifecycle(ctx, **kwargs):
    saving_non_rel_operation_info(ctx, ctx.operation.name.split('.')[-1],
                                  **kwargs)


@operation
def mock_rel_lifecycle(ctx, **kwargs):
    saving_rel_operation_info(ctx, ctx.operation.name.split('.')[-1], **kwargs)


@operation
def mock_create(ctx, **kwargs):
    saving_non_rel_operation_info(ctx, 'create', **kwargs)


@operation
def mock_configure(ctx, **kwargs):
    saving_non_rel_operation_info(ctx, 'configure', **kwargs)


@operation
def mock_start(ctx, **kwargs):
    saving_non_rel_operation_info(ctx, 'start', **kwargs)


@operation
def mock_stop(ctx, const_arg_stop=None, **kwargs):
    saving_non_rel_operation_info(ctx, 'stop', **kwargs)


@operation
def mock_stop_with_arg(ctx, const_arg_stop=None, **kwargs):
    saving_multiple_params_op(
        ctx,
        {'operation': 'stop', 'const_arg_stop': const_arg_stop},
        **kwargs
    )


@operation
def mock_delete(ctx, **kwargs):
    saving_non_rel_operation_info(ctx, 'delete', **kwargs)


@operation
def mock_preconfigure(ctx, **kwargs):
    saving_rel_operation_info(ctx, 'preconfigure', **kwargs)


@operation
def mock_postconfigure(ctx, **kwargs):
    saving_rel_operation_info(ctx, 'postconfigure', **kwargs)


@operation
def mock_establish(ctx, **kwargs):
    saving_rel_operation_info(ctx, 'establish', **kwargs)


@operation
def mock_unlink(ctx, **kwargs):
    saving_rel_operation_info(ctx, 'unlink', **kwargs)


@operation
def mock_restart(ctx, **kwargs):
    mock_operation_from_custom_workflow(ctx, 'operation', 'restart', **kwargs)


@operation
def mock_operation_get_instance_ip(ctx, **kwargs):
    with update_storage(ctx) as data:
        data['mock_operation_invocation'] = data.get(
            'mock_operation_invocation', []
        )
        data['mock_operation_invocation'].append((
            ctx.node.name, get_node_instance_ip(ctx.instance.id)
        ))

    return True


@operation
def mock_operation_get_instance_ip_from_context(ctx, **_):
    with update_storage(ctx) as data:
        data['mock_operation_invocation'] = data.get(
            'mock_operation_invocation', []
        )
        data['mock_operation_invocation'].append((
            ctx.node.name, ctx.instance.host_ip
        ))

    return True


@operation
def get_instance_ip_of_source_and_target(ctx, **_):
    with update_storage(ctx) as data:
        data['mock_operation_invocation'] = data.get(
            'mock_operation_invocation', []
        )
        data['mock_operation_invocation'].append((
            '{}_source'.format(ctx.source.node.name),
            ctx.source.instance.host_ip
        ))
        data['mock_operation_invocation'].append((
            '{}_target'.format(ctx.target.node.name),
            ctx.target.instance.host_ip
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
        data['get_resource_operation_invocation'] = data.get(
            'get_resource_operation_invocation', []
        )
        data['get_resource_operation_invocation'].append({
            'res1_data': res1_data,
            'res2_data': res2_data,
            'custom_filepath': filepath,
            'res2_path': res2
        })


@operation
def append_node_state(ctx, **kwargs):
    client = get_rest_client()
    instance = client.node_instances.get(ctx.instance.id)
    with update_storage(ctx) as data:
        data['node_states'] = data.get('node_states', [])
        data['node_states'].append(instance.state)


@operation
def sleep(ctx, **kwargs):
    sleep_time = ctx.node.properties['sleep'] if 'sleep' in\
        ctx.node.properties else kwargs['sleep']
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


class UserException(Exception):
    pass


class RecoverableUserException(RecoverableError):
    pass


class NonRecoverableUserException(NonRecoverableError):
    pass


@operation
def retry(ctx, retry_count=1, retry_after=1, **kwargs):
    with update_storage(ctx) as data:
        invocations = data.get('retry_invocations', 0)
        if invocations != ctx.operation.retry_number:
            raise NonRecoverableError(
                'invocations({0}) != ctx.operation.retry_number'
                '({1})'.format(invocations, ctx.operation.retry_number))
        data['retry_invocations'] = invocations + 1
    if ctx.operation.retry_number < retry_count:
        return ctx.operation.retry(message='Retrying operation',
                                   retry_after=retry_after)


@operation
def fail_user_exception(ctx, exception_type, **kwargs):
    with update_storage(ctx) as data:
        data['failure_invocation'] = data.get('failure_invocation', [])
        data['failure_invocation'].append(time.time())

    if exception_type == 'user_exception':
        raise UserException(
            'Failing task on user defined exception'
        )
    if exception_type == 'user_exception_recoverable':
        raise RecoverableUserException(
            'Failing task on user defined exception'
        )
    if exception_type == 'user_exception_non_recoverable':
        raise NonRecoverableUserException(
            'Failing task on user defined exception'
        )


@operation
def host_get_state(ctx, **kwargs):
    with update_storage(ctx) as data:
        data['host_get_state_invocation'] = data.get(
            'host_get_state_invocation', []
        )
        data['host_get_state_invocation'].append(time.time())

    if len(data['host_get_state_invocation']) <= get_prop('false_count',
                                                          ctx,
                                                          kwargs):
        return False
    return True


@operation
def put_workflow_node_instance(ctx,
                               modification,
                               relationships):
    with update_storage(ctx) as data:
        state = data.get('state', {})
        data['state'] = state
        state[ctx.instance.id] = {
            'node_id': ctx.node.id,
            'modification': modification,
            'relationships': relationships
        }


def get_prop(prop_name, ctx, kwargs, default=None):
    if prop_name in kwargs:
        return kwargs[prop_name]
    elif prop_name in ctx.node.properties:
        return ctx.node.properties[prop_name]
    else:
        return default


@operation
def retrieve_template(ctx, rendering_tests_demo_conf, mode, **_):
    if mode == 'get':
        resource = \
            ctx.get_resource_and_render(rendering_tests_demo_conf)
    else:
        resource = \
            ctx.download_resource_and_render(rendering_tests_demo_conf)

    with update_storage(ctx) as data:
        data['rendered_resource'] = resource

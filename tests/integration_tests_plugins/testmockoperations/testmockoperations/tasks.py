########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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
import sys
import shutil

import cloudify.utils
from cloudify.decorators import operation
from cloudify.manager import get_node_instance_ip, get_rest_client
from cloudify.exceptions import RecoverableError, NonRecoverableError


def add_invocations(instance, invocations, key='invocations'):
    """Add invocations to instance.runtime_props[key] in a safe fashion.

    Use instance.update() to allow the append to be safe in face
    of concurrent updates.
    """
    def append_invocation(old, new):
        new[key] = list(new.get(key, [])) + invocations
        return new
    instance.update(on_conflict=append_invocation)


@operation
def make_reachable(ctx, **kwargs):
    ctx.instance.runtime_properties['time'] = time.time()
    ctx.instance.runtime_properties['capabilities'] = \
        ctx.capabilities.get_all()


@operation
def make_unreachable(ctx, **kwargs):
    order = ctx.instance.runtime_properties.get('unreachable_call_order', [])
    order.append({
        'id': ctx.instance.id,
        'time': time.time()
    })
    ctx.instance.runtime_properties['unreachable_call_order'] = order


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
    del (ctx.instance.runtime_properties[property_name])


@operation
def touch(ctx, **kwargs):
    ctx.instance.runtime_properties['touched_time'] = time.time()


@operation
def start_monitor(ctx, **kwargs):
    invocations = ctx.instance.runtime_properties.get(
        'monitoring_operations_invocation', [])
    invocations.append({
        'id': ctx.instance.id,
        'operation': 'start_monitor'
    })
    ctx.instance.runtime_properties['monitoring_operations_invocation'] = \
        invocations


@operation
def stop_monitor(ctx, **kwargs):
    invocations = ctx.instance.runtime_properties.get(
        'monitoring_operations_invocation', [])
    invocations.append({
        'id': ctx.instance.id,
        'operation': 'stop_monitor'
    })
    ctx.instance.runtime_properties['monitoring_operations_invocation'] = \
        invocations


@operation
def mock_operation(ctx, **kwargs):
    mockprop = get_prop('mockprop', ctx, kwargs)
    add_invocations(ctx.instance, [{
        'id': ctx.instance.id,
        'mockprop': mockprop,
        'properties': ctx.node.properties.copy()
    }], key='mock_operation_invocation')


@operation
def mock_operation_from_custom_workflow(ctx, key, value, **kwargs):
    saving_multiple_params_op(ctx, {key: value}, **kwargs)


@operation
def saving_multiple_params_op(ctx, params, **_):
    add_invocations(
        ctx.instance, [params], key='mock_operation_invocation')


@operation
def mock_source_operation_from_custom_workflow(ctx, key, value, **_):
    add_invocations(
        ctx.source.instance, [{key: value}], key='mock_operation_invocation')


@operation
def mock_target_operation_from_custom_workflow(ctx, key, value, **_):
    add_invocations(
        ctx.target.instance, [{key: value}], key='mock_operation_invocation')


def saving_operation_info(ctx, op, main_node, second_node=None, **_):
    op_info = {'operation': op}
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

    def _append_invocation(old, new):
        key = 'mock_operation_invocation'
        new['num'] = new.get('num', 0) + 1
        op_info['num'] = new['num']
        new[key] = list(new.get(key, [])) + [op_info]
        return new
    main_node.instance.update(on_conflict=_append_invocation)

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
def mock_stop_failure(ctx, **kwargs):
    saving_non_rel_operation_info(ctx, ctx.operation.name.split('.')[-1],
                                  **kwargs)
    raise NonRecoverableError('')


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
    add_invocations(ctx.instance, [
        (ctx.node.name, get_node_instance_ip(ctx.instance.id))
    ], key='mock_operation_invocation')
    return True


@operation
def mock_operation_get_instance_ip_from_context(ctx, **_):
    add_invocations(ctx.instance, [
        (ctx.node.name, ctx.instance.host_ip)
    ], key='mock_operation_invocation')
    return True


@operation
def get_instance_ip_of_source_and_target(ctx, **_):
    add_invocations(ctx.source.instance, [
        (
            '{}_source'.format(ctx.source.node.name),
            ctx.source.instance.host_ip
        ),
        (
            '{}_target'.format(ctx.target.node.name),
            ctx.target.instance.host_ip
        )
    ], key='mock_operation_invocation')
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

    add_invocations(ctx.instance, [{
        'res1_data': res1_data,
        'res2_data': res2_data,
        'custom_filepath': filepath,
        'res2_path': res2
    }], key='get_resource_operation_invocation')


@operation
def append_node_state(ctx, **kwargs):
    client = get_rest_client()
    instance = client.node_instances.get(ctx.instance.id)

    states = ctx.instance.runtime_properties.get('node_states', [])
    states.append(instance.state)
    ctx.instance.runtime_properties['node_states'] = states


@operation
def sleep(ctx, **kwargs):
    sleep_time = (ctx.node.properties['sleep']
                  if 'sleep' in ctx.node.properties else kwargs['sleep'])
    time.sleep(int(sleep_time))


@operation
def fail(ctx, **kwargs):
    fail_count = get_prop('fail_count', ctx, kwargs, 1000000)

    invocations = ctx.instance.runtime_properties.get('failure_invocation', [])
    invocations.append(time.time())
    ctx.instance.runtime_properties['failure_invocation'] = invocations

    if len(invocations) > fail_count:
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
def retry(ctx, retry_count=1, retry_after=1, **kwargs):
    invocations = ctx.instance.runtime_properties.get('retry_invocations', 0)
    if invocations != ctx.operation.retry_number:
        raise NonRecoverableError(
            'invocations({0}) != ctx.operation.retry_number'
            '({1})'.format(invocations, ctx.operation.retry_number))
    ctx.instance.runtime_properties['retry_invocations'] = invocations + 1

    if ctx.operation.retry_number < retry_count:
        return ctx.operation.retry(message='Retrying operation',
                                   retry_after=retry_after)


@operation
def host_get_state(ctx, **kwargs):
    invocations = ctx.instance.runtime_properties.get(
        'host_get_state_invocation', [])
    add_invocations(ctx.instance, [time.time()],
                    key='host_get_state_invocation')
    return len(invocations) + 1 > get_prop('false_count', ctx, kwargs)


@operation
def put_workflow_node_instance(ctx, modification, relationships):
    state = ctx.instance.runtime_properties.get('state', {})
    state[ctx.instance.id] = {
        'node_id': ctx.node.id,
        'modification': modification,
        'relationships': relationships
    }
    ctx.instance.runtime_properties['state'] = state


def get_prop(prop_name, ctx, kwargs, default=None):
    if prop_name in kwargs:
        return kwargs[prop_name]
    elif prop_name in ctx.node.properties:
        return ctx.node.properties[prop_name]
    else:
        return default


@operation
def retrieve_template(ctx, rendering_tests_demo_conf, mode,
                      property_name='rendered_resource', **_):
    if mode == 'get':
        resource = \
            ctx.get_resource_and_render(rendering_tests_demo_conf).decode(
                'utf-8')
    else:
        resource = \
            ctx.download_resource_and_render(rendering_tests_demo_conf)
    ctx.instance.runtime_properties[property_name] = resource


@operation
def do_nothing(ctx, **kwargs):
    ctx.logger.info('dummy workflow: */(executed)+')
    return


@operation
def log(ctx, message, **kwargs):
    ctx.logger.info(message)


@operation
def write_to_workdir(ctx, filename, content):
    filepath = os.path.join(ctx.plugin.workdir, filename)
    with open(filepath, 'w') as f:
        f.write(content)


@operation
def store_scaling_groups(ctx, scaling_groups, **_):
    ctx.instance.runtime_properties['scaling_groups'] = scaling_groups


@operation
def execution_logging(ctx, user_cause=False, **_):
    ctx.logger.info('INFO_MESSAGE')
    ctx.logger.debug('DEBUG_MESSAGE')
    causes = []
    if user_cause:
        try:
            raise RuntimeError('ERROR_MESSAGE')
        except RuntimeError:
            _, ex, tb = sys.exc_info()
            causes.append(cloudify.utils.exception_to_error_cause(ex, tb))
    raise NonRecoverableError('ERROR_MESSAGE', causes=causes)


@operation
def increment_counter(ctx, **_):
    # Just a trick to have a semi-global variable inside the inner func
    tries = [0]

    def acquire_runtime_props(props, latest_props):
        tries[0] += 1
        old_counter = latest_props.get('counter', 0)
        new_counter = old_counter + 1
        ctx.logger.info(
            'Trying to update current value: '
            '{0} with new value: {1} [try number {2}]'.format(
                old_counter, new_counter, tries[0])
        )

        ctx.logger.info('Sleeping for 3 seconds...')
        time.sleep(3)
        latest_props['counter'] = new_counter
        return latest_props

    ctx.instance.update(on_conflict=acquire_runtime_props)


@operation
def write_pid_to_file_and_sleep(ctx, **kwargs):
    with open('/tmp/pid.txt', 'w') as f:
        f.write(str(os.getpid()))
    sleep(ctx, **kwargs)


@operation
def store_in_runtime_props(ctx, arg_value):
    ctx.instance.runtime_properties['arg_value'] = arg_value
    ctx.instance.runtime_properties['prop1_value'] = \
        ctx.node.properties.get('prop1')
    ctx.instance.runtime_properties['prop2_value'] = \
        ctx.node.properties.get('prop2')


@operation
def store_relationship_in_runtime_props(
        ctx, input_value=None, prop_value=None, prefix=''):
    if input_value:
        ctx.source.instance.runtime_properties[prefix + 'input_value'] = \
            input_value
        ctx.target.instance.runtime_properties[prefix + 'input_value'] = \
            input_value
    if prop_value:
        ctx.source.instance.runtime_properties[prefix + 'prop_value'] = \
            prop_value
        ctx.target.instance.runtime_properties[prefix + 'prop_value'] = \
            prop_value


@operation
def maybe_fail(ctx, should_fail=False):
    if should_fail:
        raise NonRecoverableError('Operation failed!')


@operation
def configure_connection(ctx, **kwargs):
    state = ctx.source.instance.runtime_properties.get('connection_state', {})
    state.update({
        'source_id': ctx.source.instance.id,
        'target_id': ctx.target.instance.id,
        'time': time.time(),
        'source_properties': dict(ctx.source.node.properties),
        'source_runtime_properties': dict(
            ctx.source.instance.runtime_properties),
        'target_properties': ctx.target.node.properties,
        'target_runtime_properties':
            ctx.target.instance.runtime_properties,
    })
    ctx.source.instance.runtime_properties['connection_state'] = state


@operation
def create_file_in_workdir(ctx, file_path: str, content: str):
    ctx.logger.info(f"Creating '{file_path}' in deployment workdir")
    deployment_workdir = ctx.local_deployment_workdir()
    _write_file(os.path.join(deployment_workdir, file_path), content)


@operation
def update_file_in_workdir(ctx, file_path: str, content: str):
    ctx.logger.info(f"Updating '{file_path}' in deployment workdir")
    deployment_workdir = ctx.local_deployment_workdir()
    _write_file(os.path.join(deployment_workdir, file_path), content)


@operation
def delete_file_in_workdir(ctx, file_path: str):
    ctx.logger.info(f"Deleting '{file_path}' from deployment workdir")
    deployment_workdir = ctx.local_deployment_workdir()
    os.remove(os.path.join(deployment_workdir, file_path))


def _write_file(absolute_file_path: str, content: str):
    os.makedirs(os.path.dirname(absolute_file_path), exist_ok=True)
    with open(absolute_file_path, 'wt', encoding='utf-8') as file:
        file.write(content)

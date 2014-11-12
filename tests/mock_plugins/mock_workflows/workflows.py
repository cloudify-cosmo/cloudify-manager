########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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


__author__ = 'dan'

import time
from cloudify.decorators import workflow
from cloudify.workflows import api
from cloudify.exceptions import NonRecoverableError


@workflow
def execute_operation(ctx, operation, properties, node_id, **_):
    node_instance = list(ctx.get_node(node_id).instances)[0]
    node_instance.execute_operation(
        operation=operation,
        kwargs=properties).get()


@workflow
def sleep(ctx, **kwargs):
    node_instance = get_instance(ctx)

    node_instance.execute_operation(
        'test_interface.operation',
        kwargs={'key': 'before-sleep',
                'value': None})
    node_instance.set_state('asleep')
    time.sleep(10)
    node_instance.execute_operation(
        'test_interface.operation',
        kwargs={'key': 'after-sleep',
                'value': None})


@workflow
def sleep_with_cancel_support(ctx, **kwargs):
    node_instance = get_instance(ctx)

    node_instance.execute_operation(
        'test_interface.operation',
        kwargs={'key': 'before-sleep',
                'value': None})

    node_instance.set_state('asleep')
    is_cancelled = False
    for i in range(10):
        if api.has_cancel_request():
            is_cancelled = True
            break
        time.sleep(1)

    if is_cancelled:
        return api.EXECUTION_CANCELLED_RESULT

    node_instance.execute_operation(
        'test_interface.operation',
        kwargs={'key': 'after-sleep',
                'value': None})


@workflow
def sleep_with_graph_usage(ctx, **kwargs):

    graph = ctx.graph_mode()
    sequence = graph.sequence()

    node_instance = get_instance(ctx)

    sequence.add(
        node_instance.execute_operation(
            'test_interface.operation',
            kwargs={'key': 'before-sleep',
                    'value': None}),
        node_instance.set_state('asleep'),
        node_instance.execute_operation(
            'test_interface.sleep_operation',
            kwargs={'sleep': '10'}),
        node_instance.execute_operation(
            'test_interface.operation',
            kwargs={'key': 'after-sleep',
                    'value': None}))

    return graph.execute()


@workflow
def test_simple(ctx, do_get, key, value, **_):
    instance = get_instance(ctx)
    set_state_result = instance.set_state(
        'test_state')
    if do_get:
        set_state_result.get()
    execute_operation_result = instance.execute_operation(
        'test.op1',
        kwargs={'key': key, 'value': value})
    if do_get:
        execute_operation_result.get()


@workflow
def test_cancel_on_wait_for_task_termination(ctx, do_get, **_):
    instance = get_instance(ctx)
    result = instance.execute_operation('test.sleep', kwargs={'sleep': 100000})
    if do_get:
        result.get()


@workflow
def test_cancel_on_task_retry_interval(ctx, do_get, **_):
    instance = get_instance(ctx)
    result = instance.execute_operation('test.fail')
    if do_get:
        result.get()


@workflow
def test_illegal_non_graph_to_graph_mode(ctx, **_):
    ctx.send_event('sending event')
    ctx.graph_mode()


@workflow
def test_fail_remote_task_eventual_success(ctx, do_get, **_):
    result = get_instance(ctx).execute_operation('test.op2')
    if do_get:
        result.get()


@workflow
def test_fail_remote_task_eventual_failure(ctx, do_get, **_):
    result = get_instance(ctx).execute_operation('test.op3')
    if do_get:
        result.get()


@workflow
def test_fail_local_task_eventual_success(ctx, do_get, **_):
    test_fail_local_task(ctx, should_fail=False, do_get=do_get)


@workflow
def test_fail_local_task_eventual_failure(ctx, do_get, **_):
    test_fail_local_task(ctx, should_fail=True, do_get=do_get)


def test_fail_local_task(ctx, should_fail, do_get):
    state = []

    # mock local task
    def fail():
        state.append(time.time())
        # only fail twice, succeed on the third attempt
        # (unless should_fail=True)
        if len(state) == 3 and not should_fail:
            return
        raise RuntimeError('FAIL')

    # execute the task (with retries)
    try:
        result = ctx.local_task(fail)
        if do_get:
            result.get()
    except:
        if should_fail:
            pass
        else:
            raise
    else:
        if do_get and should_fail:
            raise RuntimeError('Task should have failed')

    # make assertions
    if do_get:
        if len(state) != 3:
            raise RuntimeError('Expected 3 invocations, got {}'
                               .format(len(state)))
        for i in range(len(state) - 1):
            if state[i+1] - state[i] < 1:
                raise RuntimeError('Expected at least 1 second between each '
                                   'invocation')


@workflow
def test_fail_local_task_on_nonrecoverable_error(ctx, do_get, **_):
    state = []

    # mock local task
    def fail():
        state.append(time.time())
        raise NonRecoverableError('FAIL')

    # execute the task (with retries)
    try:
        result = ctx.local_task(fail)
        if do_get:
            result.get()
    except:
        pass
    else:
        raise RuntimeError('Task should have failed')

    # make assertions
    if do_get:
        if len(state) != 1:
            raise RuntimeError('Expected 1 invocation, got {}'
                               .format(len(state)))


@workflow
def test_policies_1(ctx, key, value,
                    custom_key=None,
                    custom_value=None,
                    **_):
    instance = list(ctx.get_node('node').instances)[0]
    instance.execute_operation('test.op1', {
        'key': key,
        'value': value,
    })
    instance.execute_operation('test.op1', {
        'key': custom_key,
        'value': custom_value
    })


@workflow
def test_policies_2(ctx, key, value, **_):
    instance = list(ctx.get_node('node').instances)[0]
    instance.execute_operation('test.op1', kwargs={
        'key': key,
        'value': value
    })


@workflow
def test_policies_3(ctx, key, value, **_):
    instance = list(ctx.get_node('node').instances)[0]
    instance.execute_operation('test.op1', kwargs={
        'key': key,
        'value': value
    })


@workflow
def auto_heal_vm(ctx, node_id, diagnose_value=None, **_):
    instance = ctx.get_node_instance(node_id)
    instance.execute_operation('test.op1', kwargs={
        'params': {
            'failing_node': node_id,
            'diagnose': diagnose_value
        }
    })


@workflow
def operation_mapping1(ctx, **_):
    node1 = list(ctx.get_node('node1').instances)[0]
    node2_rel = list(list(ctx.get_node('node2').instances)[0].relationships)[0]
    node3_rel = list(list(ctx.get_node('node3').instances)[0].relationships)[0]
    node1.execute_operation('test.operation')
    node2_rel.execute_source_operation('test.operation')
    node3_rel.execute_target_operation('test.operation')


@workflow
def operation_mapping2(ctx, value, **_):
    node1 = list(ctx.get_node('node1').instances)[0]
    node2_rel = list(list(ctx.get_node('node2').instances)[0].relationships)[0]
    node3_rel = list(list(ctx.get_node('node3').instances)[0].relationships)[0]
    node1.execute_operation('test.operation', kwargs={
        'value': value
    }, allow_kwargs_override=True)
    node2_rel.execute_source_operation('test.operation', kwargs={
        'value': value
    }, allow_kwargs_override=True)
    node3_rel.execute_target_operation('test.operation', kwargs={
        'value': value
    }, allow_kwargs_override=True)


@workflow
def operation_mapping3(ctx, value, **_):
    def expect_error(func):
        try:
            func('test.operation', kwargs={
                'value': value
            }).get()
        except RuntimeError, e:
            assert 'Duplicate' in e.message

    node1 = list(ctx.get_node('node1').instances)[0]
    node2_rel = list(list(ctx.get_node('node2').instances)[0].relationships)[0]
    node3_rel = list(list(ctx.get_node('node3').instances)[0].relationships)[0]
    expect_error(node1.execute_operation)
    expect_error(node2_rel.execute_source_operation)
    expect_error(node3_rel.execute_target_operation)


@workflow
def deployment_modification(ctx, nodes, **_):

    modification = ctx.deployment.start_modification(nodes)

    for node in modification.added.nodes:
        for instance in node.instances:
            instance.execute_operation('test.op', kwargs={
                'modification': instance.modification,
                'relationships': [(instance.id, rel.target_id)
                                  for rel in instance.relationships]
            })

    for node in modification.removed.nodes:
        for instance in node.instances:
            instance.execute_operation('test.op', kwargs={
                'modification': instance.modification,
                'relationships': [rel.target_id
                                  for rel in instance.relationships]
            })

    modification.finish()


def get_instance(ctx):
    return next(next(ctx.nodes).instances)


@workflow
def not_exist_operation_workflow(ctx, **kwargs):
    node_instance = get_instance(ctx)
    node_instance.execute_operation('test.operation')


@workflow
def not_exist_operation_graph_mode_workflow(ctx, **kwargs):
    graph = ctx.graph_mode()
    sequence = graph.sequence()
    node_instance = get_instance(ctx)
    sequence.add(node_instance.execute_operation('test.operation'))
    return graph.execute()


@workflow
def not_exist_stop_operation_workflow(ctx, **kwargs):
    node_instance = get_instance(ctx)
    node_instance.execute_operation('cloudify.interfaces.lifecycle.stop')


@workflow
def ignore_handler_on_not_exist_operation_workflow(ctx, **kwargs):
    graph = ctx.graph_mode()
    sequence = graph.sequence()
    node_instance = get_instance(ctx)
    operation = node_instance.execute_operation('test.operation')
    sequence.add(operation)

    def _ignore_on_error_handler(tsk):
        from cloudify.workflows import tasks as workflow_tasks
        return workflow_tasks.HandlerResult.ignore()
    operation.on_failure = _ignore_on_error_handler

    return graph.execute()


@workflow
def retry_handler_on_not_exist_operation_workflow(ctx, **kwargs):
    graph = ctx.graph_mode()
    sequence = graph.sequence()
    node_instance = get_instance(ctx)
    operation = node_instance.execute_operation('test.operation')
    sequence.add(operation)

    def _ignore_on_error_handler(tsk):
        from cloudify.workflows import tasks as workflow_tasks
        return workflow_tasks.HandlerResult.retry()
    operation.on_failure = _ignore_on_error_handler

    return graph.execute()


@workflow
def continue_handler_on_not_exist_operation_workflow(ctx, **kwargs):
    graph = ctx.graph_mode()
    sequence = graph.sequence()
    node_instance = get_instance(ctx)
    operation = node_instance.execute_operation('test.operation')
    sequence.add(operation)

    def _ignore_on_error_handler(tsk):
        from cloudify.workflows import tasks as workflow_tasks
        return workflow_tasks.HandlerResult.cont()
    operation.on_failure = _ignore_on_error_handler

    return graph.execute()


@workflow
def fail_handler_on_not_exist_operation_workflow(ctx, **kwargs):
    graph = ctx.graph_mode()
    sequence = graph.sequence()
    node_instance = get_instance(ctx)
    operation = node_instance.execute_operation('test.operation')
    sequence.add(operation)

    def _ignore_on_error_handler(tsk):
        from cloudify.workflows import tasks as workflow_tasks
        return workflow_tasks.HandlerResult.fail()
    operation.on_failure = _ignore_on_error_handler

    return graph.execute()

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
        'test_state', runtime_properties={key: value})
    if do_get:
        set_state_result.get()
    execute_operation_result = instance.execute_operation(
        'test.op1',
        kwargs={'key': key, 'value': value})
    if do_get:
        execute_operation_result.get()


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


def get_instance(ctx):
    return next(next(ctx.nodes).instances)

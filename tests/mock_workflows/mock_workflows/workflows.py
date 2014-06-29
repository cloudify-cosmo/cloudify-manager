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
        node_instance.execute_operation(
            'test_interface.sleep_operation',
            kwargs={'sleep': '10'}),
        node_instance.execute_operation(
            'test_interface.operation',
            kwargs={'key': 'after-sleep',
                    'value': None}))

    return graph.execute()


@workflow
def test_simple(ctx, key, value, **_):
    instance = get_instance(ctx)
    instance.set_state('test_state',
                       runtime_properties={key: value}).get()
    instance.execute_operation('test.op1',
                               kwargs={'key': key, 'value': value}).get()


@workflow
def test_fail_remote_task(ctx, **_):
    instance = get_instance(ctx)
    instance.execute_operation('test.op2').get()


@workflow
def test_fail_local_task(ctx, **_):
    instance = get_instance(ctx)
    instance.execute_operation('test.op2').get()


def get_instance(ctx):
    return next(next(ctx.nodes).instances)

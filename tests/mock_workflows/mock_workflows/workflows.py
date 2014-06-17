__author__ = 'dan'

from cloudify.decorators import workflow


@workflow
def execute_operation(ctx, operation, properties, node_id, **_):
    node_instance = list(ctx.get_node(node_id).instances)[0]
    node_instance.execute_operation(
        operation=operation,
        kwargs=properties).apply_async().get()

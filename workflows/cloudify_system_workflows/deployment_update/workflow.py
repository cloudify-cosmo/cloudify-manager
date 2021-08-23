from cloudify.decorators import workflow
from cloudify.state import workflow_ctx
from cloudify.manager import get_rest_client


def create_update(*, update_id, new_inputs):
    client = get_rest_client()
    dep = client.deployments.get(workflow_ctx.deployment.id)

    inputs = dep.inputs.copy()
    inputs.update(new_inputs)

    client.deployment_updates.create(
        update_id,
        workflow_ctx.deployment.id,
        inputs=inputs
    )


def _prepare_update_graph(
        ctx,
        update_id,
        *,
        inputs=None,
        **kwargs):
    graph = ctx.graph_mode()
    seq = graph.sequence()
    seq.add(
        ctx.local_task(create_update, kwargs={
            'update_id': update_id,
            'new_inputs': inputs or {},
        }, total_retries=0),
    )
    return graph


@workflow
def update_deployment(ctx, **kwargs):
    client = get_rest_client()
    update_id = '{0}_{1}'.format(ctx.deployment.id, ctx.execution_id)
    graph = _prepare_update_graph(ctx, update_id, **kwargs)
    graph.execute()

    client.deployment_updates.set_attributes(
        update_id,
        state='successful'
    )

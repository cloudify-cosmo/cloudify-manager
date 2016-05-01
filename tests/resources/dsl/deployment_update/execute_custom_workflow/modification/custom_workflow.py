from cloudify.workflows import ctx, parameters
from cloudify.manager import get_rest_client

instance = [n for n in ctx.node_instances][0]
instance.execute_operation('custom_lifecycle.custom_operation',
                           kwargs={'update_id': parameters.update_id})

rest_client = get_rest_client()
rest_client.deployment_updates.finalize_commit(parameters.update_id)

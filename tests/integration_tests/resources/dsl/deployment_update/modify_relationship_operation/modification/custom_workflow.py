
from cloudify.workflows import ctx, parameters


ctx.logger.info(parameters.node_id)

instance = [n for n in ctx.node_instances
            if n.node_id == parameters.node_id][0]

for relationship in instance.relationships:
    relationship.execute_source_operation('custom_lifecycle.custom_operation')

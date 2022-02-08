from cloudify.state import ctx
from cloudify.state import ctx_parameters as inputs

ctx.logger.info(f"Deployment: id={ctx.deployment.id}, "
                f"display_name={ctx.deployment.display_name}, "
                f"creator={ctx.deployment.creator}")
ctx.logger.info(f"Resource tags: {ctx.deployment.resource_tags}")

if not ctx.deployment.resource_tags:
    ctx.abort_operation("There are no resource_tags defined")

for k, v in inputs['values'].items():
    if k not in ctx.deployment.resource_tags:
        ctx.abort_operation(f"There's no '{k}' resource_tag")
    if ctx.deployment.resource_tags[k] != v:
        ctx.abort_operation(f"Expected resource_tags[{k}] == {v}, got: "
                            f"{ctx.deployment.resource_tags[k]}")

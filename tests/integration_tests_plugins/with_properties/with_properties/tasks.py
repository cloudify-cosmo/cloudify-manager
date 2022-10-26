from yaml import safe_dump

from cloudify.decorators import operation


@operation
def op(ctx, **_):
    output_file_name = f'/tmp/execution-{ctx.execution_id}-{ctx.node.id}.yaml'
    ctx.logger.info(f'Performing OP and writing output to {output_file_name}')
    msg = {k: v.get('value') for k, v in ctx.plugin.properties.items()}
    with open(output_file_name, 'a+') as fh:
        safe_dump(msg, fh)

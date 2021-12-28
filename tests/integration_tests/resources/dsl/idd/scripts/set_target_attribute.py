from cloudify import ctx
from cloudify.state import ctx_parameters

ctx.instance.runtime_properties['prop1'] = ctx_parameters['target_id']

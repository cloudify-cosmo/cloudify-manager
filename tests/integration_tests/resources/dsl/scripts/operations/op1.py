
from cloudify import ctx
from cloudify.state import ctx_parameters as p


ctx.instance.runtime_properties['op1_called_with_property'] = p.property

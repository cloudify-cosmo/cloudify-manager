
from cloudify import ctx
from cloudify.state import ctx_parameters as p


ctx.instance.runtime_properties['update_id'] = p.update_id

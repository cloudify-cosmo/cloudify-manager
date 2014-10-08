from cloudify import ctx
from cloudify.state import ctx_parameters as p

from testenv.utils import update_storage

with update_storage(ctx) as data:
    data['op2_prop'] = ctx.instance.runtime_properties['op2_prop']
    data['op1_called_with_property'] = p.property


from cloudify import ctx


IS_OP_STARTED = 'is_op_started'


ctx.target.instance.runtime_properties[IS_OP_STARTED] = \
    ctx.source.instance.runtime_properties[IS_OP_STARTED]

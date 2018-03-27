
from time import sleep

from cloudify import ctx
from cloudify.manager import get_rest_client


IS_OP_STARTED = 'is_op_started'


if ctx.node.id == 'site2':
    # TODO: is there a better way, except sleep?
    sleep(5)
    site3 = get_rest_client().node_instances.list(node_id='site3').items[0]
    ctx.instance.runtime_properties[IS_OP_STARTED] = \
        site3.runtime_properties.get(IS_OP_STARTED, False)
else:   # ctx.node.id == 'site3'
    ctx.instance.runtime_properties[IS_OP_STARTED] = True

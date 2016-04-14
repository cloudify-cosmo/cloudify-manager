from cloudify import ctx

from testenv.utils import update_storage

with update_storage(ctx) as data:
    data['op3_called'] = True

from cloudify import ctx

from mock_plugins.utils import update_storage

with update_storage(ctx) as data:
    data['op3_called'] = True

#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from functools import wraps

from cloudify import utils
from cloudify.context import CloudifyContext

from windows_agent_installer import utils as winrm_utils


__author__ = 'elip'


def init_worker_installer(func):

    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = utils.find_type_in_kwargs(CloudifyContext, kwargs.values() + list(args))
        if not ctx:
            raise RuntimeError('CloudifyContext not found in invocation args')
        if ctx.properties and 'worker_config' in ctx.properties:
            worker_config = ctx.properties['worker_config']
        else:
            worker_config = {}
        prepare_configuration(ctx, worker_config)
        kwargs['worker_config'] = worker_config
        kwargs['runner'] = winrm_utils.WinRMRunner(ctx, worker_config)
        return func(*args, **kwargs)
    return wrapper


def prepare_configuration(ctx, worker_config):

    # validations

    if 'user' not in worker_config:
        raise ValueError('Missing user in worker configuration')

    if 'password' not in worker_config:
        raise ValueError('Missing password in worker configuration')

    # defaults

    if 'port' not in worker_config:
        worker_config['port'] = winrm_utils.DEFAULT_WINRM_PORT
    if 'protocol' not in worker_config:
        worker_config['protocol'] = winrm_utils.DEFAULT_WINRM_PROTOCOL
    if 'uri' not in worker_config:
        worker_config['uri'] = winrm_utils.DEFAULT_WINRM_URI
    if 'base_dir' not in worker_config:
        worker_config['base_dir'] = 'C:\Users\{0}'.format(worker_config['user'])

    # runtime info

    worker_config['name'] = ctx.node_id
    worker_config['host'] = utils.get_machine_ip(ctx)


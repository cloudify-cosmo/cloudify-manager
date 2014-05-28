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

__author__ = 'idanmo'

import os
import cloudify
from functools import wraps
from worker_installer.utils import (FabricRunner,
                                    is_on_management_worker)

DEFAULT_MIN_WORKERS = 2
DEFAULT_MAX_WORKERS = 5
DEFAULT_REMOTE_EXECUTION_PORT = 22


def _find_type_in_kwargs(cls, all_args):
    result = [v for v in all_args if isinstance(v, cls)]
    if not result:
        return None
    if len(result) > 1:
        raise RuntimeError(
            "Expected to find exactly one instance of {0} in "
            "kwargs but found {1}".format(cls, len(result)))
    return result[0]


def init_worker_installer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = _find_type_in_kwargs(cloudify.context.CloudifyContext,
                                   kwargs.values() + list(args))
        if not ctx:
            raise RuntimeError('CloudifyContext not found in invocation args')
        if ctx.properties and 'worker_config' in ctx.properties:
            worker_config = ctx.properties['worker_config']
        else:
            worker_config = {}
        prepare_configuration(ctx, worker_config)
        kwargs['worker_config'] = worker_config
        kwargs['runner'] = FabricRunner(ctx, worker_config)
        return func(*args, **kwargs)
    return wrapper


def get_machine_ip(ctx):
    if 'ip' in ctx.properties:
        return ctx.properties['ip']
    if 'ip' in ctx.runtime_properties:
        return ctx.runtime_properties['ip']
    raise ValueError(
        'ip property is not set for node: {0}. This is mandatory'
        ' for installing agent via ssh.'.format(ctx.node_id))


def _prepare_and_validate_autoscale_params(ctx, config):
    if 'min_workers' not in config and\
            ctx.bootstrap_context.cloudify_agent.min_workers:
        config['min_workers'] = \
            ctx.bootstrap_context.cloudify_agent.min_workers
    if 'max_workers' not in config and\
            ctx.bootstrap_context.cloudify_agent.max_workers:
        config['max_workers'] = \
            ctx.bootstrap_context.cloudify_agent.max_workers

    min_workers = config.get('min_workers', DEFAULT_MIN_WORKERS)
    max_workers = config.get('max"workers', DEFAULT_MAX_WORKERS)

    if not str(min_workers).isdigit():
        raise ValueError('min_workers is supposed to be a number '
                         'but is: {0}'.format(min_workers))
    if not str(max_workers).isdigit():
        raise ValueError('max_workers is supposed to be a number '
                         'but is: {0}'.format(max_workers))
    min_workers = int(min_workers)
    max_workers = int(max_workers)
    if int(min_workers) > int(max_workers):
        raise ValueError('min_workers cannot be greater than max_workers '
                         '[min_workers={0}, max_workers={1}]'
                         .format(min_workers, max_workers))
    config['min_workers'] = min_workers
    config['max_workers'] = max_workers


def _set_ssh_key(ctx, config):
    if 'key' not in config:
        if ctx.bootstrap_context.cloudify_agent.agent_key_path:
            config['key'] = ctx.bootstrap_context.cloudify_agent.agent_key_path
        else:
            raise ValueError(
                'Missing ssh key path in worker configuration '
                '[worker_config={0}'.format(config))


def _set_user(ctx, config):
    if 'user' not in config:
        if ctx.bootstrap_context.cloudify_agent.user:
            config['user'] = ctx.bootstrap_context.cloudify_agent.user
        else:
            raise ValueError(
                'Missing user in worker configuration '
                '[worker_config={0}'.format(config))


def _set_remote_execution_port(ctx, config):
    if 'remote_execution_port' not in config:
        if ctx.bootstrap_context.cloudify_agent.remote_execution_port:
            config['port'] =\
                ctx.bootstrap_context.cloudify_agent.remote_execution_port
        else:
            config['port'] = DEFAULT_REMOTE_EXECUTION_PORT


def prepare_configuration(ctx, worker_config):
    if is_on_management_worker(ctx):
        # we are starting a worker dedicated for a deployment
        # (not specific node)
        # use the same user we used when bootstrapping
        if 'MANAGEMENT_USER' in os.environ:
            worker_config['user'] = os.environ['MANAGEMENT_USER']
        else:
            raise RuntimeError('Cannot determine user for deployment user:'
                               'MANAGEMENT_USER is not set')
        workflows_worker = worker_config['workflows_worker']\
            if 'workflows_worker' in worker_config else 'false'
        suffix = '_workflows' if workflows_worker.lower() == 'true' else ''
        name = '{0}{1}'.format(ctx.deployment_id, suffix)
        worker_config['name'] = name
    else:
        worker_config['host'] = get_machine_ip(ctx)
        _set_ssh_key(ctx, worker_config)
        _set_user(ctx, worker_config)
        _set_remote_execution_port(ctx, worker_config)
        worker_config['name'] = ctx.node_id

    home_dir = "/home/" + worker_config['user'] \
        if worker_config['user'] != 'root' else '/root'

    worker_config['celery_base_dir'] = home_dir

    worker_config['base_dir'] = '{0}/cloudify.{1}'.format(
        home_dir, worker_config['name'])
    worker_config['init_file'] = '/etc/init.d/celeryd-{0}'.format(
        worker_config['name'])
    worker_config['config_file'] = '/etc/default/celeryd-{0}'.format(
        worker_config['name'])
    worker_config['includes_file'] = '{0}/work/celeryd-includes'.format(
        worker_config['base_dir'])

    disable_requiretty = True
    if 'disable_requiretty' in worker_config:
        disable_requiretty_value = str(
            worker_config['disable_requiretty']).lower()
        if disable_requiretty_value.lower() == 'true':
            disable_requiretty = True
        elif disable_requiretty_value.lower() == 'false':
            disable_requiretty = False
        else:
            raise ValueError(
                'Value for disable_requiretty property should be true/false '
                'but is: {0}'.format(disable_requiretty_value))
    worker_config['disable_requiretty'] = disable_requiretty
    _prepare_and_validate_autoscale_params(ctx, worker_config)

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


import os
import pwd
from functools import wraps

import cloudify
from cloudify.exceptions import NonRecoverableError

from worker_installer.utils import (FabricRunner,
                                    is_on_management_worker)

DEFAULT_MIN_WORKERS = 2
DEFAULT_MAX_WORKERS = 5
DEFAULT_REMOTE_EXECUTION_PORT = 22
DEFAULT_WAIT_STARTED_TIMEOUT = 15
DEFAULT_WAIT_STARTED_INTERVAL = 1


def _find_type_in_kwargs(cls, all_args):
    result = [v for v in all_args if isinstance(v, cls)]
    if not result:
        return None
    if len(result) > 1:
        raise NonRecoverableError(
            "Expected to find exactly one instance of {0} in "
            "kwargs but found {1}".format(cls, len(result)))
    return result[0]


def init_worker_installer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = _find_type_in_kwargs(cloudify.context.CloudifyContext,
                                   kwargs.values() + list(args))
        if not ctx:
            raise NonRecoverableError(
                'CloudifyContext not found in invocation args')
        if ctx.node.properties and 'cloudify_agent' in ctx.node.properties:
            agent_config = ctx.node.properties['cloudify_agent']
        else:
            agent_config = kwargs.get('cloudify_agent', {})
        prepare_configuration(ctx, agent_config)
        kwargs['agent_config'] = agent_config
        kwargs['runner'] = FabricRunner(ctx, agent_config)
        if not agent_config.get('distro'):
            kwargs['agent_config']['distro'] = \
                get_machine_distro(kwargs['runner'])
        return func(*args, **kwargs)
    return wrapper


def get_machine_distro(runner):
    return runner.run(
        'python -c "import platform; print(platform.dist()[0])"')


def get_machine_ip(ctx):
    if ctx.node.properties.get('ip'):
        return ctx.node.properties['ip']
    if 'ip' in ctx.instance.runtime_properties:
        return ctx.instance.runtime_properties['ip']
    raise NonRecoverableError(
        'ip property is not set for node: {0}. This is mandatory'
        ' for installing agent via ssh.'.format(ctx.instance.id))


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
    max_workers = config.get('max_workers', DEFAULT_MAX_WORKERS)

    if not str(min_workers).isdigit():
        raise NonRecoverableError('min_workers is supposed to be a number '
                                  'but is: {0}'.format(min_workers))
    if not str(max_workers).isdigit():
        raise NonRecoverableError('max_workers is supposed to be a number '
                                  'but is: {0}'.format(max_workers))
    min_workers = int(min_workers)
    max_workers = int(max_workers)
    if int(min_workers) > int(max_workers):
        raise NonRecoverableError(
            'min_workers cannot be greater than max_workers '
            '[min_workers={0}, max_workers={1}]'
            .format(min_workers, max_workers))
    config['min_workers'] = min_workers
    config['max_workers'] = max_workers


def _set_ssh_key(ctx, config):
    if 'key' not in config:
        if ctx.bootstrap_context.cloudify_agent.agent_key_path:
            config['key'] = ctx.bootstrap_context.cloudify_agent.agent_key_path
        else:
            raise NonRecoverableError(
                'Missing ssh key path in worker configuration '
                '[cloudify_agent={0}'.format(config))

    if not os.path.isfile(os.path.expanduser(config['key'])):
        raise NonRecoverableError(
            'Cannot find keypair file, expected file path was {'
            '0}'.format(config['key']))


def _set_user(ctx, config):
    if 'user' not in config:
        if ctx.bootstrap_context.cloudify_agent.user:
            config['user'] = ctx.bootstrap_context.cloudify_agent.user
        else:
            raise NonRecoverableError(
                'Missing user in worker configuration '
                '[cloudify_agent={0}'.format(config))


def _set_remote_execution_port(ctx, config):
    if 'port' not in config:
        if ctx.bootstrap_context.cloudify_agent.remote_execution_port:
            config['port'] =\
                ctx.bootstrap_context.cloudify_agent.remote_execution_port
        else:
            config['port'] = DEFAULT_REMOTE_EXECUTION_PORT


def _set_wait_started_config(config):
    if 'wait_started_timeout' not in config:
        config['wait_started_timeout'] = DEFAULT_WAIT_STARTED_TIMEOUT
    if 'wait_started_interval' not in config:
        config['wait_started_interval'] = DEFAULT_WAIT_STARTED_INTERVAL


def prepare_configuration(ctx, agent_config):
    if is_on_management_worker(ctx):
        # we are starting a worker dedicated for a deployment
        # (not specific node)
        # use the same user we used when bootstrapping
        if 'MANAGEMENT_USER' in os.environ:
            agent_config['user'] = os.environ['MANAGEMENT_USER']
        else:
            raise NonRecoverableError(
                'Cannot determine user for deployment user:'
                'MANAGEMENT_USER is not set')
        workflows_worker = agent_config['workflows_worker']\
            if 'workflows_worker' in agent_config else False
        suffix = '_workflows' if workflows_worker else ''
        name = '{0}{1}'.format(ctx.deployment.id, suffix)
        agent_config['name'] = name
    else:
        agent_config['host'] = get_machine_ip(ctx)
        _set_ssh_key(ctx, agent_config)
        _set_user(ctx, agent_config)
        _set_remote_execution_port(ctx, agent_config)
        agent_config['name'] = ctx.instance.id

    _set_wait_started_config(agent_config)

    home_dir = pwd.getpwnam(agent_config['user']).pw_dir

    agent_config['celery_base_dir'] = home_dir

    agent_config['base_dir'] = '{0}/cloudify.{1}'.format(
        home_dir, agent_config['name'])
    agent_config['init_file'] = '/etc/init.d/celeryd-{0}'.format(
        agent_config['name'])
    agent_config['config_file'] = '/etc/default/celeryd-{0}'.format(
        agent_config['name'])
    agent_config['includes_file'] = '{0}/work/celeryd-includes'.format(
        agent_config['base_dir'])

    disable_requiretty = True
    if 'disable_requiretty' in agent_config:
        disable_requiretty_value = str(
            agent_config['disable_requiretty']).lower()
        if disable_requiretty_value.lower() == 'true':
            disable_requiretty = True
        elif disable_requiretty_value.lower() == 'false':
            disable_requiretty = False
        else:
            raise NonRecoverableError(
                'Value for disable_requiretty property should be true/false '
                'but is: {0}'.format(disable_requiretty_value))
    agent_config['disable_requiretty'] = disable_requiretty
    _prepare_and_validate_autoscale_params(ctx, agent_config)

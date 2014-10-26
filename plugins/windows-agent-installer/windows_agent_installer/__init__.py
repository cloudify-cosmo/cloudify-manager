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
from cloudify.exceptions import NonRecoverableError

from windows_agent_installer import constants
from windows_agent_installer.winrm_runner import WinRMRunner


def init_worker_installer(func):

    """
    Decorator for initializing the worker.
    Injects the following arguments to the decorated function:

        1. runner - WinRMRunner instance for executing
                    remote commands on a windows machine.

        2. cloudify_agent - agent configuration. This dictionary
                            will be augmented with default values
                            and go through a validation process.

    :param func: The function to inject the parameters with.
    :return: the decorator.
    :rtype: function
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = utils.find_type_in_kwargs(CloudifyContext,
                                        kwargs.values() + list(args))
        if not ctx:
            raise RuntimeError('CloudifyContext not found in invocation args')
        if ctx.node.properties and 'cloudify_agent' in ctx.node.properties:
            cloudify_agent = ctx.node.properties['cloudify_agent']
        else:
            cloudify_agent = {}
        prepare_configuration(ctx, cloudify_agent)
        kwargs['cloudify_agent'] = cloudify_agent
        try:
            kwargs['runner'] = WinRMRunner(
                session_config=cloudify_agent.copy(),
                logger=ctx.logger)
            return func(*args, **kwargs)
        except ValueError as e:
            raise NonRecoverableError('Failed instantiating WinRMRunner: {0}'
                                      .format(e.message))
    return wrapper


def prepare_configuration(ctx, cloudify_agent):

    """
    Sets default and runtime values to the cloudify_agent.
    Also performs validation on these values.

    :param ctx: The invocation context.
    :param cloudify_agent: The cloudify_agent configuration dict.
    """

    set_bootstrap_context_parameters(ctx.bootstrap_context, cloudify_agent)
    set_service_configuration_parameters(cloudify_agent)
    set_agent_configuration_parameters(cloudify_agent)

    # runtime info
    cloudify_agent['name'] = ctx.instance.id
    cloudify_agent['host'] = _get_machine_ip(ctx)


def set_bootstrap_context_parameters(bootstrap_context, cloudify_agent):

    """
    Sets parameters that were passed during the bootstrap process.
    The semantics should always be:

        1. Parameters in the cloudify agent configuration if specified.
        2. Parameter in the bootstrap context.
        3. default value.

    :param bootstrap_context:

        The bootstrap context from the 'cloudify'
        section in the cloudify-config.yaml

    :param cloudify_agent: configuration dictionary.
    """
    set_autoscale_parameters(bootstrap_context, cloudify_agent)


def set_agent_configuration_parameters(cloudify_agent):

    # defaults
    _set_default(cloudify_agent,
                 constants.AGENT_START_TIMEOUT_KEY,
                 15)
    _set_default(cloudify_agent,
                 constants.AGENT_START_INTERVAL_KEY,
                 1)


def set_service_configuration_parameters(cloudify_agent):

    # defaults
    _set_default(cloudify_agent,
                 'service',
                 {})
    _set_default(cloudify_agent['service'],
                 constants.SERVICE_FAILURE_RESET_TIMEOUT_KEY,
                 60)
    _set_default(cloudify_agent['service'],
                 constants.SERVICE_FAILURE_RESTART_DELAY_KEY,
                 5000)

    # validations
    for key in cloudify_agent['service'].iterkeys():
        _validate_digit(
            'cloudify_agent.service.{0}'.format(key),
            cloudify_agent['service'][key])


def set_autoscale_parameters(bootstrap_context, cloudify_agent):
    if constants.MIN_WORKERS_KEY not in cloudify_agent and\
       bootstrap_context.cloudify_agent.min_workers:
        cloudify_agent[constants.MIN_WORKERS_KEY] =\
            bootstrap_context.cloudify_agent.min_workers
    if constants.MAX_WORKERS_KEY not in cloudify_agent and\
       bootstrap_context.cloudify_agent.max_workers:
        cloudify_agent[constants.MAX_WORKERS_KEY] =\
            bootstrap_context.cloudify_agent.max_workers

    min_workers = cloudify_agent.get(constants.MIN_WORKERS_KEY, 2)
    max_workers = cloudify_agent.get(constants.MAX_WORKERS_KEY, 5)

    _validate_digit(constants.MIN_WORKERS_KEY, min_workers)
    _validate_digit(constants.MAX_WORKERS_KEY, max_workers)

    min_workers = int(min_workers)
    max_workers = int(max_workers)
    if int(min_workers) > int(max_workers):
        raise NonRecoverableError(
            '{0} cannot be greater than {2} '
            '[{0}={1}, {2}={3}]' .format(
                constants.MIN_WORKERS_KEY,
                min_workers,
                max_workers,
                constants.MAX_WORKERS_KEY))
    cloudify_agent[constants.MIN_WORKERS_KEY] = min_workers
    cloudify_agent[constants.MAX_WORKERS_KEY] = max_workers


def _validate_digit(name, value):
    if not str(value).isdigit():
        raise NonRecoverableError('{0} is supposed to be a number '
                                  'but is: {1}'.format(name, value))


def _set_default(dictionary, key, value):
    if key not in dictionary:
        dictionary[key] = value


def _get_machine_ip(ctx):
    if ctx.node.properties.get('ip'):
        return ctx.node.properties['ip']
    if 'ip' in ctx.instance.runtime_properties:
        return ctx.instance.runtime_properties['ip']
    raise NonRecoverableError(
        'ip property is not set for node: {0}. This is mandatory'
        ' for manipulating a remote agent.'.format(ctx.instance.id))

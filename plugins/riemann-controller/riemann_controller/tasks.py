#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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
import time
import errno
import json
import subprocess
from os import path

import requests
import pika

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError, HttpException
from cloudify.manager import get_resource

from riemann_controller import config

RIEMANN_CONFIGS_DIR = 'RIEMANN_CONFIGS_DIR'
RIEMANN_LOG_PATH = '/tmp/riemann.log'


@operation
def create(policy_types=None,
           policy_triggers=None,
           groups=None,
           **_):

    policy_types = policy_types or {}
    groups = groups or {}
    policy_triggers = policy_triggers or {}

    _process_types_and_triggers(groups, policy_types, policy_triggers)
    deployment_config_dir_path = _deployment_config_dir()
    if not os.path.isdir(deployment_config_dir_path):
        os.makedirs(deployment_config_dir_path)
        os.chmod(deployment_config_dir_path, 0777)
    with open(_deployment_config_template()) as f:
        deployment_config_template = f.read()
    with open(os.path.join(_deployment_config_dir(), 'groups'), 'w') as f:
        f.write(json.dumps(groups))
    with open(path.join(deployment_config_dir_path,
                        'deployment.config'), 'w') as f:
        f.write(config.create(ctx,
                              policy_types,
                              policy_triggers,
                              groups,
                              deployment_config_template))
    _publish_configuration_event('start', deployment_config_dir_path)
    _verify_core_up(deployment_config_dir_path)


@operation
def delete(**_):
    deployment_config_dir_path = _deployment_config_dir()
    _publish_configuration_event('stop', deployment_config_dir_path)


def _deployment_config_dir():
    return os.path.join(os.environ[RIEMANN_CONFIGS_DIR],
                        ctx.deployment_id)


def _publish_configuration_event(state, deployment_config_dir_path):
    manager_queue = 'manager-riemann'
    exchange_name = 'cloudify-monitoring'
    connection = pika.BlockingConnection()
    try:
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange_name,
                                 type='topic',
                                 durable=False,
                                 auto_delete=True,
                                 internal=False)
        channel.queue_declare(
            queue=manager_queue,
            auto_delete=True,
            durable=False,
            exclusive=False)
        channel.queue_bind(exchange=exchange_name,
                           queue=manager_queue,
                           routing_key=manager_queue)
        channel.basic_publish(
            exchange=exchange_name,
            routing_key=manager_queue,
            body=json.dumps({
                'service': 'cloudify.configuration',
                'state': state,
                'config_path': deployment_config_dir_path,
                'deployment_id': ctx.deployment_id,
                'time': int(time.time())
            }))
    finally:
        connection.close()


def _deployment_config_template():
    return path.abspath(path.join(path.dirname(__file__),
                                  'resources',
                                  'deployment.config.template'))


def _verify_core_up(deployment_config_dir_path):
    timeout = ctx.bootstrap_context.policy_engine.start_timeout or 30
    ok_path = path.join(deployment_config_dir_path, 'ok')
    end = time.time() + timeout
    while time.time() < end:
        try:
            # after the core is started this file is written as an indication
            with (open(ok_path)):
                pass
            return
        except IOError, e:
            if e.errno in [errno.ENOENT]:
                time.sleep(0.5)
            else:
                raise

    try:
        riemann_log_output = subprocess.check_output(
            'tail -n 100 {}'.format(RIEMANN_LOG_PATH), shell=True)
    except Exception as e:
        riemann_log_output = 'Failed extracting log: {0}'.format(e)

    raise NonRecoverableError('Riemann core has not started in {} seconds.\n'
                              'tail -n 100 {}:\n {}'
                              .format(timeout,
                                      RIEMANN_LOG_PATH,
                                      riemann_log_output))


def _process_types_and_triggers(groups, policy_types, policy_triggers):
    types_to_process = set()
    types_to_remove = set()
    triggers_to_process = set()
    triggers_to_remove = set()
    for group in groups.values():
        for policy in group['policies'].values():
            types_to_process.add(policy['type'])
            for trigger in policy['triggers'].values():
                triggers_to_process.add(trigger['type'])
    for policy_type_name, policy_type in policy_types.items():
        if policy_type_name in types_to_process:
            policy_type['source'] = _process_source(policy_type['source'])
        else:
            types_to_remove.add(policy_type_name)
    for policy_trigger_name, trigger in policy_triggers.items():
        if policy_trigger_name in triggers_to_process:
            trigger['source'] = _process_source(trigger['source'])
        else:
            triggers_to_remove.add(policy_trigger_name)
    for policy_type_name in types_to_remove:
        del policy_types[policy_type_name]
    for trigger_type_name in triggers_to_remove:
        del policy_triggers[trigger_type_name]


def _process_source(source):
    split = source.split('://')
    schema = split[0]
    the_rest = ''.join(split[1:])

    try:
        if schema in ['http', 'https']:
            return requests.get(source).text
        elif schema == 'file' and the_rest:
            with open(the_rest) as f:
                return f.read()
    except IOError, e:
        raise NonRecoverableError('Failed processing source: {} ({})'
                                  .format(source, e.message))

    try:
        # try downloading blueprint resource
        return ctx.get_resource(source)
    except HttpException:
        pass
    try:
        # try downloading cloudify resource
        return get_resource(source)
    except HttpException:
        pass
    raise NonRecoverableError('Failed processing source: {}'
                              .format(source))

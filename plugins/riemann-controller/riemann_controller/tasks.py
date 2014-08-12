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
import shutil
from os import path
import socket
import time
import errno

import requests
import bernhard

from cloudify.decorators import operation

from riemann_controller import config

RIEMANN_CONFIGS_DIR = 'RIEMANN_CONFIGS_DIR'


@operation
def create(ctx, policy_types=None, groups=None, **kwargs):
    policy_types = policy_types or {}
    groups = groups or {}
    _process_policy_type_sources(ctx, policy_types)
    deployment_config_dir_path = _deployment_config_dir(ctx)
    if not os.path.isdir(deployment_config_dir_path):
        os.makedirs(deployment_config_dir_path)
    with open(_deployment_config_template()) as f:
        deployment_config_template = f.read()
    with open(path.join(deployment_config_dir_path,
                        'deployment.config'), 'w') as f:
        f.write(config.create(ctx,
                              policy_types,
                              groups,
                              deployment_config_template))
    _send_configuration_event('start', deployment_config_dir_path)
    _verify_core_up(deployment_config_dir_path)


@operation
def delete(ctx, **kwargs):
    deployment_config_dir_path = _deployment_config_dir(ctx)
    _send_configuration_event('stop', deployment_config_dir_path)


def _deployment_config_dir(ctx):
    return os.path.join(os.environ[RIEMANN_CONFIGS_DIR],
                        ctx.deployment_id)


def _send_configuration_event(state, deployment_config_dir_path):
    bernhard.Client().send({
        'service': 'cloudify.configuration',
        'state': state,
        'description': deployment_config_dir_path,
    })


def _deployment_config_template():
    return path.abspath(path.join(path.dirname(__file__),
                                  'resources',
                                  'deployment.config.template'))


def _verify_core_up(deployment_config_dir_path, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        try:
            # if we managed to read the port properly, it is an indication
            # that riemann started the core successfully. otherwise, it would
            # delete this file and rethrow the exception it caught while trying
            # to start the core
            with (open(path.join(deployment_config_dir_path, 'port'))) as f:
                port = int(f.read())
            sock = socket.socket()
            sock.connect(('localhost', port))
            sock.close()
            return
        except IOError, e:
            if e.errno in [errno.ENOENT, errno.ECONNREFUSED]:
                time.sleep(0.1)
            else:
                raise
    raise RuntimeError('Riemann was has not started in {} seconds'
                       .format(timeout))


def _process_policy_type_sources(ctx, policy_types):
    for policy_type in policy_types.values():
        policy_type['source'] = _process_source(ctx, policy_type['source'])


def _process_source(ctx, source):
    split = source.split('://')
    schema = split[0]
    the_rest = ''.join(split[1:])
    if schema in ['http', 'https']:
        return requests.get(source).text
    elif schema == 'file':
        with open(the_rest) as f:
            return f.read()
    elif schema == 'resource':
        return ctx.get_resource(the_rest)
    elif schema == 'blueprint':
        return ctx.get_blueprint_resource(the_rest)
    else:
        return source

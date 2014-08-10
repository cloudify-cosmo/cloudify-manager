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

import bernhard

from cloudify.decorators import operation

RIEMANN_CONFIGS_DIR = 'RIEMANN_CONFIGS_DIR'


@operation
def create(ctx, **kwargs):
    deployment_config_dir_path = _deployment_config_dir(ctx)
    if not os.path.isdir(deployment_config_dir_path):
        os.makedirs(deployment_config_dir_path)
    shutil.copy(_deployment_config(),
                path.join(deployment_config_dir_path, 'deployment.config'))
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


def _deployment_config():
    return path.abspath(path.join(path.dirname(__file__),
                                  'resources', 'deployment.config'))


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
            break
        except IOError, e:
            if e.errno in [errno.ENOENT, errno.ECONNREFUSED]:
                time.sleep(0.1)
            else:
                raise

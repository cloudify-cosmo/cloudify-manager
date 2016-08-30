########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import

import os
import socket
import sys
import time
import tempfile
from functools import partial

import requests.exceptions
import pika
import pika.exceptions
import proxy_tools
import sh
import yaml

import cloudify_rest_client.exceptions

import testenv
from testenv import constants
from testenv import utils

# All container specific docl commands that are executed with no explicit
# container id will be executed on the default_container_id which is set
# after the manager container is started on run_manager()
default_container_id = None


# Using proxies because the sh.Command needs to be baked with an environment
# variable telling it where to find the custom docl conf which is only
# generated after the test environment is instantiated.


def _docl_proxy(quiet=False):
    env = os.environ.copy()
    env['DOCL_HOME'] = _docl_home()
    result = sh.docl.bake(_env=env)
    if not quiet:
        result = result.bake(_err_to_out=True,
                             _out=lambda l: sys.stdout.write(l),
                             _tee=True)

    return result
_docl = proxy_tools.Proxy(_docl_proxy)
_quiet_docl = proxy_tools.Proxy(partial(_docl_proxy, quiet=True))


def _docl_home():
    from testenv import testenv_instance
    return os.path.join(testenv_instance.test_working_dir, 'docl')


def _build_config(
        additional_expose=None,
        additional_resources=None):
    """
    For each test suite, we augment the existing docl configuration
    with additional ports that need to be exposed and custom directories
    that need to be mounted

    :param additional_expose: List of ports
    :param additional_resources: List of {'src':'', 'dst':''} dicts
    """
    docl_home = _docl_home()
    work_dir = os.path.join(docl_home, 'work')
    if not os.path.exists(docl_home):
        os.makedirs(docl_home)
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)
    with open(os.path.expanduser('~/.docl/config.yaml')) as f:
        conf = yaml.safe_load(f)
    conf['expose'] += (additional_expose or [])
    conf['resources'] += (additional_resources or [])
    conf['workdir'] = work_dir
    with open(os.path.join(docl_home, 'config.yaml'), 'w') as f:
        yaml.safe_dump(conf, f)


def run_manager(label=None, resources=None):
    start = time.time()
    label = label or []
    _build_config(additional_resources=resources)
    args = ['--mount']
    for l in label:
        args += ['--label', l]
    with tempfile.NamedTemporaryFile() as f:
        args += ['--details-path', f.name]
        _docl.run(*args)
        with open(f.name) as f2:
            container_details = yaml.safe_load(f2)
    global default_container_id
    default_container_id = container_details['id']
    os.environ[constants.DOCL_CONTAINER_IP] = container_details['ip']
    _wait_for_services()
    testenv.logger.info(
        'Container start took {0} seconds'.format(time.time() - start))


def _retry(func, exceptions, cleanup=None):
    for _ in range(600):
        try:
            res = func()
            if cleanup:
                cleanup(res)
            break
        except exceptions:
            time.sleep(0.1)
    else:
        raise


def _wait_for_services():
    container_ip = utils.get_manager_ip()
    testenv.logger.info('Waiting for RabbitMQ')
    _retry(func=utils.create_pika_connection,
           exceptions=pika.exceptions.AMQPConnectionError,
           cleanup=lambda conn: conn.close())
    testenv.logger.info('Waiting for REST service and Storage')
    rest_client = utils.create_rest_client()
    _retry(func=rest_client.blueprints.list,
           exceptions=(requests.exceptions.ConnectionError,
                       cloudify_rest_client.exceptions.CloudifyClientError))
    testenv.logger.info('Waiting for logstash')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _retry(func=lambda: sock.connect((container_ip, 9999)),
           cleanup=lambda _: sock.close(),
           exceptions=IOError)
    testenv.logger.info('Waiting for postgres')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _retry(func=lambda: sock.connect((container_ip, 5432)),
           cleanup=lambda _: sock.close(),
           exceptions=IOError)


def clean(label=None):
    label = label or []
    args = []
    for l in label:
        args += ['--label', l]
    _docl.clean(*args)


def read_file(file_path, no_strip=False, container_id=None):
    container_id = container_id or default_container_id
    result = _quiet_docl('exec', 'cat {0}'.format(file_path),
                         container_id=container_id)
    if not no_strip:
        result = result.strip()
    return result


def docker_host():
    with open(os.path.join(_docl_home(), 'config.yaml')) as f:
        config = yaml.safe_load(f)
    return config['docker_host']


def execute(command, quiet=True, container_id=None):
    container_id = container_id or default_container_id
    proc = _quiet_docl if quiet else _docl
    return proc('exec', command, container_id=container_id)


def copy_file_to_manager(source, target, container_id=None):
    container_id = container_id or default_container_id
    return _quiet_docl('cp', source, ':{0}'.format(target),
                       container_id=container_id)


def install_docker(container_id=None):
    container_id = container_id or default_container_id
    return _docl('install-docker', container_id=container_id)


def build_agent(container_id=None):
    container_id = container_id or default_container_id
    return _docl('build-agent', container_id=container_id)

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
import sh
import sys
import yaml
import time
import socket
import tempfile

from functools import partial

import proxy_tools
import requests.exceptions
from pika.exceptions import AMQPConnectionError

import cloudify_rest_client.exceptions
import cloudify.utils

from integration_tests.framework import utils, constants
from integration_tests.framework.constants import INSERT_MOCK_LICENSE_QUERY


# All container specific docl commands that are executed with no explicit
# container id will be executed on the default_container_id which is set
# after the manager container is started on run_manager()
default_container_id = None

logger = cloudify.utils.setup_logger('docl')


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
    from integration_tests.framework import env
    if env.instance:
        return os.path.join(env.instance.test_working_dir, 'docl')
    else:
        # When working outside of the tests framework
        return os.path.expanduser('~/.docl')


def _load_docl_config():
    with open(os.path.join(_docl_home(), 'config.yaml')) as f:
        return yaml.safe_load(f)


def _save_docl_config(conf):
    with open(os.path.join(_docl_home(), 'config.yaml'), 'w') as f:
        yaml.safe_dump(conf, f)


def _get_docl_config_property(key):
    config = _load_docl_config()
    return config[key]


def docker_host():
    return _get_docl_config_property('docker_host')


def init(expose=None, resources=None):
    """
    For each test suite, we augment the existing docl configuration
    with additional ports that need to be exposed and custom directories
    that need to be mounted

    :param expose: List of ports
    :param resources: List of {'src':'', 'dst':''} dicts
    """
    docl_home = _docl_home()
    resource_tar_name = 'cloudify-manager-resources.tar.gz'
    work_dir = os.path.join(docl_home, 'work')
    if not os.path.exists(docl_home):
        os.makedirs(docl_home)
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)
    with open(os.path.expanduser('~/.docl/config.yaml')) as f:
        conf = yaml.safe_load(f)
    resources_tar_path = os.path.join(conf['workdir'], resource_tar_name)
    if os.path.exists(resources_tar_path):
        os.symlink(resources_tar_path,
                   os.path.join(work_dir, resource_tar_name))
    conf['expose'] += list(expose or [])
    conf['resources'] += list(resources or [])
    conf['workdir'] = work_dir
    _save_docl_config(conf)


def run_manager(label=None, tag=None):
    start = time.time()
    label = label or []
    args = ['--mount']
    if tag:
        args += ['--tag', tag]
    for l in label:
        args += ['--label', l]
    with tempfile.NamedTemporaryFile() as f:
        args += ['--details-path', f.name]
        _docl.run(*args)
        with open(f.name) as f2:
            container_details = yaml.safe_load(f2)
    _set_container_id_and_ip(container_details)
    utils.update_profile_context()
    upload_mock_license()
    _wait_for_services()
    logger.info(
        'Container start took {0} seconds'.format(time.time() - start))
    return container_details


def upload_mock_license():
    execute(('sudo -u postgres psql cloudify_db '
             '-c "{0}"'.format(INSERT_MOCK_LICENSE_QUERY)))


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


def execute(command, quiet=True, container_id=None):
    container_id = container_id or default_container_id
    proc = _quiet_docl if quiet else _docl
    return proc('exec', command, container_id=container_id)


def copy_file_to_manager(source, target, container_id=None):
    container_id = container_id or default_container_id
    return _quiet_docl('cp', source, ':{0}'.format(target),
                       container_id=container_id)


def copy_file_from_manager(source, target, container_id=None):
    container_id = container_id or default_container_id
    return _quiet_docl('cp', ':{0}'.format(source), target,
                       container_id=container_id)


def install_docker(container_id=None):
    container_id = container_id or default_container_id
    return _docl('install-docker', container_id=container_id)


def build_agent(container_id=None):
    container_id = container_id or default_container_id
    return _docl('build-agent', container_id=container_id)


def _set_container_id_and_ip(container_details):
    global default_container_id
    default_container_id = container_details['id']
    os.environ[constants.DOCL_CONTAINER_IP] = container_details['ip']


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
        raise RuntimeError()


def _wait_for_services(container_ip=None):
    if container_ip is None:
        container_ip = utils.get_manager_ip()
    logger.info('Waiting for RabbitMQ')
    _retry(func=utils.create_pika_connection,
           exceptions=AMQPConnectionError,
           cleanup=lambda conn: conn.close())
    logger.info('Waiting for REST service and Storage')
    rest_client = utils.create_rest_client()
    _retry(func=rest_client.blueprints.list,
           exceptions=(requests.exceptions.ConnectionError,
                       cloudify_rest_client.exceptions.CloudifyClientError))
    logger.info('Waiting for postgres')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _retry(func=lambda: sock.connect((container_ip, 5432)),
           cleanup=lambda _: sock.close(),
           exceptions=IOError)

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
import shlex
import logging
import tempfile
import subprocess
from functools import partial

import proxy_tools
import cloudify.utils

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


def _save_docl_container_details(container_details):
    with open(
            os.path.join(
                _docl_home(), 'work', 'last_container_ip'), 'w') as outfile:
        outfile.write(container_details['ip'])
    with open(
            os.path.join(
                _docl_home(), 'work', 'last_container_id'), 'w') as outfile:
        outfile.write(container_details['id'])


def _get_docl_config_property(key):
    config = _load_docl_config()
    return config[key]


def _get_docl_container_details():
    container_details = {}
    with open(
            os.path.join(_docl_home(), 'work', 'last_container_ip')) as infile:
        container_details['id'] = infile.read()
    with open(
            os.path.join(_docl_home(), 'work', 'last_container_id')) as infile:
        container_details['ip'] = infile.read()
    return container_details


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


def run_manager(image, service_management, resource_mapping=None,):
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as conf:
        conf.write("""
manager:
    security:
        admin_password: admin
validations:
    skip_validations: true
sanity:
    skip_sanity: true
service_management: {0}
""".format(service_management))
    command = [
        'docker', 'run', '-d',
        '-v', '/sys/fs/cgroup:/sys/fs/cgroup:ro',
        '-v', '{0}:/etc/cloudify/config.yaml:rw'.format(conf.name),
        '--tmpfs', '/run', '--tmpfs', '/run/lock',
    ]
    if resource_mapping:
        for src, dst in resource_mapping:
            command += ['-v', '{0}:{1}:ro'.format(src, dst)]
    command += [image]
    logging.info('Starting container: %s', ' '.join(command))
    manager_id = subprocess.check_output(command).decode('utf-8').strip()
    logging.info('Started container %s', manager_id)
    execute(manager_id, ['cfy_manager', 'wait-for-starter'])
    return manager_id


def upload_mock_license(manager_id):
    execute(
        manager_id,
        'sudo -u postgres psql cloudify_db -c "{0}"'
        .format(INSERT_MOCK_LICENSE_QUERY)
    )


def clean(container_id):
    subprocess.check_call(['docker', 'rm', '-f', container_id])


def read_file(container_id, file_path, no_strip=False):
    result = subprocess.check_output([
        'docker', 'exec', container_id, 'cat', file_path
    ]).decode('utf-8')
    if not no_strip:
        result = result.strip()
    return result


def execute(container_id, command, env=None):
    if not isinstance(command, list):
        command = shlex.split(command)
    args = ['docker', 'exec']
    if not env:
        env = {}
    # assume utf-8 - for decoding the output, and so ask the executables
    # to use utf-8 indeed
    env.setdefault('LC_ALL', 'en_US.UTF-8')
    for k, v in env.items():
        args += ['-e', '{0}={1}'.format(k, v)]
    args.append(container_id)
    return subprocess.check_output(args + command).decode('utf-8')


def copy_file_to_manager(container_id, source, target):
    subprocess.check_call([
        'docker', 'cp', source, '{0}:{1}'.format(container_id, target)
    ])


def copy_file_from_manager(container_id, source, target):
    subprocess.check_call([
        'docker', 'cp', '{0}:{1}'.format(container_id, source), target
    ])


def get_manager_ip(container_id):
    return subprocess.check_output([
        'docker', 'inspect',
        '--format={{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
        container_id
    ]).decode('utf-8').strip()


def file_exists(container_id, file_path):
    try:
        execute(container_id, 'test -e {0}'.format(file_path))
    except subprocess.CalledProcessError:
        return False

    return True

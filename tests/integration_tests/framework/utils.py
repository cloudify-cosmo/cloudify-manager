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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
import sys
import time
import json
import yaml
import tempfile
import shutil
from functools import wraps
from collections import namedtuple
from multiprocessing import Process

import influxdb
import pika
import sh
from wagon import wagon

from manager_rest.utils import create_auth_header
from cloudify_cli import env as cli_env
from cloudify_cli.constants import CLOUDIFY_USERNAME_ENV, CLOUDIFY_PASSWORD_ENV
from cloudify_rest_client import CloudifyClient
from cloudify.utils import setup_logger
from integration_tests.framework import constants

logger = setup_logger('testenv.utils')


def _write(stream, s):
    try:
        s = s.encode('utf-8')
    except UnicodeDecodeError:
        pass
    stream.write(s)


def sh_bake(command):
    return command.bake(
            _out=lambda line: _write(sys.stdout, line),
            _err=lambda line: _write(sys.stderr, line))


def get_manager_ip():
    return os.environ[constants.DOCL_CONTAINER_IP]


def get_username():
    return os.environ[CLOUDIFY_USERNAME_ENV]


def get_password():
    return os.environ[CLOUDIFY_PASSWORD_ENV]


def create_rest_client(**kwargs):
    # Doing it with kwargs instead of arguments with default values to allow
    # not passing args (which will then use the default values), or explicitly
    # passing None (or False) which will then be passed as-is to the Client

    username = kwargs.get('username', get_username())
    password = kwargs.get('password', get_password())
    token = kwargs.get('token')
    rest_port = kwargs.get('rest_port',
                           os.environ.get(constants.CLOUDIFY_REST_PORT, 80))
    rest_protocol = kwargs.get('rest_protocol',
                               'https' if rest_port == '443' else 'http')
    cert_path = kwargs.get('cert_path', cli_env.get_ssl_cert())
    trust_all = kwargs.get('trust_all', cli_env.get_ssl_trust_all())

    headers = create_auth_header(username, password, token)

    return CloudifyClient(
            host=get_manager_ip(),
            port=rest_port,
            protocol=rest_protocol,
            headers=headers,
            trust_all=trust_all,
            cert=cert_path)


def get_postgres_client_details():
    details = namedtuple('PGDetails', 'db_name username password host')
    return details('cloudify_db',
                   'cloudify',
                   'cloudify',
                   get_manager_ip())


def create_influxdb_client():
    return influxdb.InfluxDBClient(get_manager_ip(), 8086,
                                   'root', 'root', 'cloudify')


def create_pika_connection():
    credentials = pika.credentials.PlainCredentials(
        username='cloudify',
        password='c10udify')
    return pika.BlockingConnection(
        pika.ConnectionParameters(host=get_manager_ip(),
                                  credentials=credentials))


def get_cfy():
    return sh.cfy.bake(_err_to_out=True,
                       _out=lambda l: sys.stdout.write(l),
                       _tee=True)


def timeout(seconds=60):
    def decorator(func):
        def wrapper(*args, **kwargs):
            process = Process(None, func, None, args, kwargs)
            process.start()
            process.join(seconds)
            if process.is_alive():
                process.terminate()
                raise TimeoutException(
                    'test timeout exceeded [timeout={0}'.format(seconds))
        return wraps(func)(wrapper)
    return decorator


def timestamp():
    now = time.strftime("%c")
    return now.replace(' ', '-')


class TimeoutException(Exception):

    def __init__(self, message):
        Exception.__init__(self, message)

    def __str__(self):
        return self.message


def _create_mock_wagon(package_name, package_version):
    module_src = tempfile.mkdtemp(
        prefix='plugin-{0}-'.format(package_name))
    try:
        with open(os.path.join(module_src, 'setup.py'), 'w') as f:
            f.write('from setuptools import setup\n')
            f.write('setup(name="{0}", version={1})'.format(
                package_name, package_version))
        wagon_client = wagon.Wagon(module_src)
        result = wagon_client.create(
            archive_destination_dir=tempfile.gettempdir(),
            force=True)
    finally:
        shutil.rmtree(module_src)
    return result


class YamlPatcher(object):

    pattern = re.compile("(.+)\[(\d+)\]")
    set_pattern = re.compile("(.+)\[(\d+|append)\]")

    def __init__(self, yaml_path, is_json=False, default_flow_style=True):
        self.yaml_path = yaml_path
        with open(self.yaml_path) as f:
            self.obj = yaml.load(f) or {}
        self.is_json = is_json
        self.default_flow_style = default_flow_style

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            output = json.dumps(self.obj) if self.is_json else yaml.safe_dump(
                    self.obj, default_flow_style=self.default_flow_style)
            with open(self.yaml_path, 'w') as f:
                f.write(output)

    def merge_obj(self, obj_prop_path, merged_props):
        obj = self._get_object_by_path(obj_prop_path)
        for key, value in merged_props.items():
            obj[key] = value

    def set_value(self, prop_path, new_value):
        obj, prop_name = self._get_parent_obj_prop_name_by_path(prop_path)
        list_item_match = self.set_pattern.match(prop_name)
        if list_item_match:
            prop_name = list_item_match.group(1)
            obj = obj[prop_name]
            if not isinstance(obj, list):
                raise AssertionError('Cannot set list value for not list item '
                                     'in {0}'.format(prop_path))
            raw_index = list_item_match.group(2)
            if raw_index == 'append':
                obj.append(new_value)
            else:
                obj[int(raw_index)] = new_value
        else:
            obj[prop_name] = new_value

    def append_value(self, prop_path, value):
        obj, prop_name = self._get_parent_obj_prop_name_by_path(prop_path)
        obj[prop_name] = obj[prop_name] + value

    def _split_path(self, path):
        # allow escaping '.' with '\.'
        parts = re.split('(?<![^\\\\]\\\\)\.', path)
        return [p.replace('\.', '.').replace('\\\\', '\\') for p in parts]

    def _get_object_by_path(self, prop_path):
        current = self.obj
        for prop_segment in self._split_path(prop_path):
            match = self.pattern.match(prop_segment)
            if match:
                index = int(match.group(2))
                property_name = match.group(1)
                if property_name not in current:
                    self._raise_illegal(prop_path)
                if type(current[property_name]) != list:
                    self._raise_illegal(prop_path)
                current = current[property_name][index]
            else:
                if prop_segment not in current:
                    current[prop_segment] = {}
                current = current[prop_segment]
        return current

    def delete_property(self, prop_path, raise_if_missing=True):
        obj, prop_name = self._get_parent_obj_prop_name_by_path(prop_path)
        if prop_name in obj:
            obj.pop(prop_name)
        elif raise_if_missing:
            raise KeyError('cannot delete property {0} as its not a key in '
                           'object {1}'.format(prop_name, obj))

    def _get_parent_obj_prop_name_by_path(self, prop_path):
        split = self._split_path(prop_path)
        if len(split) == 1:
            return self.obj, prop_path
        parent_path = '.'.join(p.replace('.', '\.') for p in split[:-1])
        parent_obj = self._get_object_by_path(parent_path)
        prop_name = split[-1]
        return parent_obj, prop_name

    @staticmethod
    def _raise_illegal(prop_path):
        raise RuntimeError('illegal path: {0}'.format(prop_path))


def get_admin_user():
    return [
        {
            'username': cli_env.get_username(),
            'password': cli_env.get_password(),
            'roles': ['administrator']
        }
    ]

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
import shutil
import zipfile
import tempfile
import requests

from functools import wraps
from multiprocessing import Process
from contextlib import contextmanager

import sh
import pika

from . import constants

from cloudify.utils import setup_logger
from cloudify_rest_client import CloudifyClient
from manager_rest.utils import create_auth_header

from cloudify_cli import env as cli_env
from cloudify_cli.constants import CLOUDIFY_BASE_DIRECTORY_NAME

from . import docker


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


def get_profile_context(container_id):
    profile_context_cmd = 'cat /root/.cloudify/profiles/localhost/context.json'
    return json.loads(docker.execute(container_id, profile_context_cmd))


def set_cfy_paths(new_workdir):
    cli_env.CLOUDIFY_WORKDIR = os.path.join(
        new_workdir,
        CLOUDIFY_BASE_DIRECTORY_NAME
    )
    cli_env.PROFILES_DIR = os.path.join(cli_env.CLOUDIFY_WORKDIR, 'profiles')
    cli_env.ACTIVE_PRO_FILE = os.path.join(
        cli_env.CLOUDIFY_WORKDIR,
        'active.profile'
    )


def create_rest_client(host, **kwargs):
    # Doing it with kwargs instead of arguments with default values to allow
    # not passing args (which will then use the default values), or explicitly
    # passing None (or False) which will then be passed as-is to the Client

    username = kwargs.get('username', 'admin')
    password = kwargs.get('password', 'admin')
    tenant = kwargs.get('tenant', 'default_tenant')
    token = kwargs.get('token')
    rest_port = kwargs.get('rest_port',
                           os.environ.get(constants.CLOUDIFY_REST_PORT, 80))
    rest_protocol = kwargs.get('rest_protocol',
                               'https' if rest_port == '443' else 'http')
    cert_path = kwargs.get('cert_path', cli_env.get_ssl_cert())
    trust_all = kwargs.get('trust_all', cli_env.get_ssl_trust_all())

    headers = create_auth_header(username, password, token, tenant)

    return CloudifyClient(
        host=host,
        port=rest_port,
        protocol=rest_protocol,
        headers=headers,
        trust_all=trust_all,
        cert=cert_path)


def create_pika_connection(host):
    credentials = pika.credentials.PlainCredentials(
        username='cloudify',
        password='c10udify')
    return pika.BlockingConnection(
        pika.ConnectionParameters(host=host,
                                  port=5671,
                                  ssl=True,
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
                    'test timeout exceeded [timeout={0}]'.format(seconds))
            if process.exitcode != 0:
                raise RuntimeError('{} ended with exception'.format(func))
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


@contextmanager
def zip_files(files):
    source_folder = tempfile.mkdtemp()
    destination_zip = source_folder + '.zip'
    for path in files:
        shutil.copy(path, source_folder)
    create_zip(source_folder, destination_zip, include_folder=False)
    shutil.rmtree(source_folder)
    try:
        yield destination_zip
    finally:
        os.remove(destination_zip)


def unzip(archive, destination):
    with zipfile.ZipFile(archive, 'r') as zip_file:
        zip_file.extractall(destination)


def create_zip(source, destination, include_folder=True):
    with zipfile.ZipFile(destination, 'w') as zip_file:
        for root, _, files in os.walk(source):
            for filename in files:
                file_path = os.path.join(root, filename)
                source_dir = os.path.dirname(source) if include_folder \
                    else source
                zip_file.write(
                    file_path, os.path.relpath(file_path, source_dir))
    return destination


def download_file(file_url, tmp_file):
    logger.info('Retrieving file: {0}'.format(file_url))
    response = requests.get(file_url, stream=True)
    with open(tmp_file, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return tmp_file


class YamlPatcher(object):

    pattern = re.compile(r'(.+)\[(\d+)\]')
    set_pattern = re.compile(r'(.+)\[(\d+|append)\]')

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
        parts = re.split(r'(?<![^\\\\]\\\\)\.', path)
        return [p.replace(r'\.', '.').replace('\\\\', '\\') for p in parts]

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
        parent_path = '.'.join(p.replace('.', r'\.') for p in split[:-1])
        parent_obj = self._get_object_by_path(parent_path)
        prop_name = split[-1]
        return parent_obj, prop_name

    @staticmethod
    def _raise_illegal(prop_path):
        raise RuntimeError('illegal path: {0}'.format(prop_path))

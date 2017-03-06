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


import StringIO
import errno
import json
import os
import platform
import shutil
import sys
import traceback
from base64 import urlsafe_b64encode
from datetime import datetime
from os import path, makedirs

import wagon.utils
from flask_restful import abort

from manager_rest import constants, config

CLOUDIFY_AUTH_HEADER = 'Authorization'
CLOUDIFY_AUTH_TOKEN_HEADER = 'Authentication-Token'
CLOUDIFY_API_AUTH_TOKEN_HEADER = 'API-Authentication-Token'
BASIC_AUTH_PREFIX = 'Basic '


def copy_resources(file_server_root, resources_path=None):
    if resources_path is None:
        resources_path = path.abspath(__file__)
        for i in range(3):
            resources_path = path.dirname(resources_path)
        resources_path = path.join(resources_path, 'resources')
    cloudify_resources = path.join(resources_path,
                                   'rest-service',
                                   'cloudify')
    shutil.copytree(cloudify_resources, path.join(file_server_root,
                                                  'cloudify'))


def abort_error(error, logger, hide_server_message=False):
    logger.info('{0}: {1}'.format(type(error).__name__, str(error)))
    s_traceback = StringIO.StringIO()
    if hide_server_message:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_tb(exc_traceback, file=s_traceback)
    else:
        traceback.print_exc(file=s_traceback)

    abort(error.http_code,
          message=str(error),
          error_code=error.error_code,
          server_traceback=s_traceback.getvalue())


def mkdirs(folder_path):
    try:
        makedirs(folder_path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and path.isdir(folder_path):
            pass
        else:
            raise


def create_filter_params_list_description(parameters, list_type):
    return [{'name': filter_val,
             'description': 'List {type} matching the \'{filter}\' '
                            'filter value'.format(type=list_type,
                                                  filter=filter_val),
             'required': False,
             'allowMultiple': False,
             'dataType': 'string',
             'defaultValue': None,
             'paramType': 'query'} for filter_val in parameters]


def read_json_file(file_path):
    with open(file_path) as f:
        return json.load(f)


def write_dict_to_json_file(file_path, dictionary):
    with open(file_path, 'w') as f:
        json.dump(dictionary, f)


def is_bypass_maintenance_mode(request):
    bypass_maintenance_header = 'X-BYPASS-MAINTENANCE'
    return request.headers.get(bypass_maintenance_header)


def get_plugin_archive_path(plugin_id, archive_name):
    return os.path.join(
        config.instance.file_server_root,
        constants.FILE_SERVER_PLUGINS_FOLDER,
        plugin_id,
        archive_name
    )


def plugin_installable_on_current_platform(plugin):
    dist, _, release = platform.linux_distribution(
            full_distribution_name=False)
    dist, release = dist.lower(), release.lower()

    # Mac OSX is a special case, in which plugin.distribution and
    # plugin.release will be None instead of ''
    if 'macosx' in plugin.supported_platform:
        dist = dist or None
        release = release or None

    return (plugin.supported_platform == 'any' or all([
        plugin.supported_platform == wagon.utils.get_platform(),
        plugin.distribution == dist,
        plugin.distribution_release == release
    ]))


def get_formatted_timestamp():
    # Adding 'Z' to match ISO format
    return '{0}Z'.format(datetime.now().isoformat()[:-3])


class classproperty(object):
    """A class that acts a a decorator for class-level properties

    class A(object):
        _prop1 = 1
        _prop2 = 2

        @classproperty
        def foo(cls):
            return cls._prop1 + cls._prop2

    And use it like this:
    print A.foo  # 3

    """
    def __init__(self, get_func):
        self.get_func = get_func

    def __get__(self, _, owner_cls):
        return self.get_func(owner_cls)


def create_auth_header(username=None, password=None, token=None, tenant=None):
    """Create a valid authentication header either from username/password or
    a token if any were provided; return an empty dict otherwise
    """
    headers = {}
    if username and password:
        credentials = '{0}:{1}'.format(username, password)
        headers = {CLOUDIFY_AUTH_HEADER:
                   BASIC_AUTH_PREFIX + urlsafe_b64encode(credentials)}
    elif token:
        headers = {CLOUDIFY_AUTH_TOKEN_HEADER: token}
    if tenant:
        headers[constants.CLOUDIFY_TENANT_HEADER] = tenant
    return headers

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
import sys
import glob
import json
import errno
import shutil
import zipfile
import StringIO
import tempfile
import platform
import traceback
from functools import wraps
from datetime import datetime
from os import path, makedirs
from base64 import urlsafe_b64encode

import wagon
from flask import g, current_app
from flask_restful import abort
from flask_security import current_user
from werkzeug.local import LocalProxy
from opentracing_instrumentation.request_context import get_current_span, \
    span_in_context

from cloudify import logs
from cloudify.amqp_client import create_events_publisher
from manager_rest import constants, config, manager_exceptions


CLOUDIFY_AUTH_HEADER = 'Authorization'
CLOUDIFY_AUTH_TOKEN_HEADER = 'Authentication-Token'
CLOUDIFY_API_AUTH_TOKEN_HEADER = 'API-Authentication-Token'
BASIC_AUTH_PREFIX = 'Basic '


MODELS_TO_PERMISSIONS = {'NodeInstance': 'node_instance'}


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

    abort(error.status_code,
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
        plugin.supported_platform == wagon.get_platform(),
        plugin.distribution == dist,
        plugin.distribution_release == release
    ]))


def get_formatted_timestamp():
    # Adding 'Z' to match ISO format
    return '{0}Z'.format(datetime.now().isoformat()[:-3])


class classproperty(object):  # NOQA  # class CapWords
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


def all_tenants_authorization():
    return (
        current_user.id == constants.BOOTSTRAP_ADMIN_ID or
        any(r in current_user.system_roles
            for r in config.instance.authorization_permissions['all_tenants'])
    )


def tenant_specific_authorization(tenant, resource_name, action='list'):
    """
    Return true if the user is permitted to perform a certain action in a
    in a given tenant on a given resource (for filtering purpose).
    """
    resource_name = MODELS_TO_PERMISSIONS.get(resource_name,
                                              resource_name.lower())
    permission_name = '{0}_{1}'.format(resource_name, action)
    return current_user.has_role_in(
        tenant, config.instance.authorization_permissions[permission_name])


def is_administrator(tenant):
    administrators_roles = \
        config.instance.authorization_permissions['administrators']
    return (
        current_user.id == constants.BOOTSTRAP_ADMIN_ID or
        current_user.has_role_in(tenant, administrators_roles)
    )


def is_create_global_permitted(tenant):
    create_global_roles = \
        config.instance.authorization_permissions['create_global_resource']
    return (
        current_user.id == constants.BOOTSTRAP_ADMIN_ID or
        current_user.has_role_in(tenant, create_global_roles)
    )


@LocalProxy
def current_tenant():
    tenant = getattr(g, 'current_tenant', None)
    if not tenant:
        raise manager_exceptions.TenantNotProvided(
            'Authorization failed: tenant not provided')
    return tenant


def set_current_tenant(tenant):
    g.current_tenant = tenant


def unzip(archive, destination=None, logger=None):
    if not destination:
        destination = tempfile.mkdtemp()
    if logger:
        logger.debug('Extracting zip {0} to {1}...'.
                     format(archive, destination))
    with zipfile.ZipFile(archive, 'r') as zip_file:
        zip_file.extractall(destination)
    return destination


def files_in_folder(folder, name_pattern='*'):
    files = []
    for item in glob.glob(os.path.join(folder, name_pattern)):
        if os.path.isfile(item):
            files.append(os.path.join(folder, item))
    return files


def remove(path):
    if os.path.exists(path):
        if os.path.isfile(path):
            os.remove(path)
        else:
            shutil.rmtree(path)


def send_event(event, message_type):
    logs.populate_base_item(event, 'cloudify_event')
    events_publisher = create_events_publisher(
        amqp_host=config.instance.amqp_host,
        amqp_user=config.instance.amqp_username,
        amqp_pass=config.instance.amqp_password,
        amqp_port=constants.BROKER_SSL_PORT,
        amqp_vhost='/',
        ssl_enabled=True,
        ssl_cert_path=config.instance.amqp_ca_path
    )

    events_publisher.publish_message(event, message_type)
    events_publisher.close()


def with_tracing(func_name=None):
    """Wrapper function for Flask operation call tracing.
    This decorator must be activate iff the following condition apply. One of
    the parent calls must be done inside a 'with span_in_context(span)' scope
    (otherwise you'd get a parentless span).

    :param name: name to display in tracing
    """

    def decorator(f):
        name = func_name
        if func_name is None:
            name = f.__name__

        @wraps(f)
        def with_tracing_wrapper(*args, **kwargs):
            root_span = get_current_span()
            with current_app.tracer.start_span(
                    name,
                    child_of=root_span) as span:
                with span_in_context(span):
                    return f(*args, **kwargs)

        return with_tracing_wrapper

    return decorator

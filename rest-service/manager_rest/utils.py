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
from datetime import datetime
from os import path, makedirs
from base64 import urlsafe_b64encode

import wagon
from flask import g
from flask import request
from flask_restful import abort
from werkzeug.local import LocalProxy
from flask_security import current_user

from cloudify import logs
from cloudify.constants import BROKER_PORT_SSL
from cloudify.models_states import VisibilityState
from cloudify.amqp_client import create_events_publisher

from manager_rest import constants, config, manager_exceptions


def check_allowed_endpoint(allowed_endpoints):
    for endpoint in allowed_endpoints:
        if endpoint in request.endpoint:
            return True
    return False


def is_sanity_mode():
    return os.path.isfile(constants.SANITY_MODE_FILE_PATH)


def is_internal_request():
    remote_addr = _get_remote_addr()
    http_hosts = [_get_host(), constants.LOCAL_ADDRESS]
    return all([remote_addr, http_hosts, remote_addr in http_hosts])


def _get_host():
    return request.host


def _get_remote_addr():
    return request.remote_addr


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

    return (plugin.supported_platform in ('any', 'manylinux1_x86_64') or all([
        plugin.supported_platform == wagon.get_platform(),
        plugin.distribution == dist,
        plugin.distribution_release == release
    ]))


def get_formatted_timestamp():
    # Adding 'Z' to match ISO format
    return '{0}Z'.format(datetime.utcnow().isoformat()[:-3])


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
        headers = {constants.CLOUDIFY_AUTH_HEADER:
                   constants.BASIC_AUTH_PREFIX + urlsafe_b64encode(credentials)
                   }
    elif token:
        headers = {constants.CLOUDIFY_AUTH_TOKEN_HEADER: token}
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
    resource_name = constants.MODELS_TO_PERMISSIONS.get(resource_name,
                                                        resource_name.lower())
    try:
        permission_name = '{0}_{1}'.format(resource_name, action)
        permission_roles = \
            config.instance.authorization_permissions[permission_name]
    except KeyError:
        permission_roles = \
            config.instance.authorization_permissions[resource_name.lower()]
    return current_user.has_role_in(tenant, permission_roles)


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


def can_execute_global_workflow(tenant):
    execute_global_roles = \
        config.instance.authorization_permissions['execute_global_workflow']
    return (
            current_user.id == constants.BOOTSTRAP_ADMIN_ID or
            current_user.has_role_in(tenant, execute_global_roles)
    )


def validate_global_modification(resource):
    # A global resource can't be modify from outside its tenant
    if resource.visibility == VisibilityState.GLOBAL and \
       resource.tenant_name != current_tenant.name:
        raise manager_exceptions.IllegalActionError(
            "Can't modify the global resource `{0}` from outside its "
            "tenant `{1}`".format(resource.id, resource.tenant_name))


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
        amqp_port=BROKER_PORT_SSL,
        amqp_vhost='/',
        ssl_enabled=True,
        ssl_cert_path=config.instance.amqp_ca_path
    )

    events_publisher.publish_message(event, message_type)
    events_publisher.close()


def is_visibility_wider(first, second):
    states = VisibilityState.STATES
    return states.index(first) > states.index(second)


def validate_deployment_and_site_visibility(deployment, site):
    if is_visibility_wider(deployment.visibility, site.visibility):
        raise manager_exceptions.IllegalActionError(
            "The visibility of deployment `{0}`: `{1}` can't be wider than "
            "the visibility of it's site `{2}`: `{3}`"
            .format(deployment.id, deployment.visibility, site.name,
                    site.visibility)
        )

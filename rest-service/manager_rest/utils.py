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


import json
import os
import sys
import shutil
import traceback
import StringIO
import errno
import platform
from datetime import datetime
from os import path, makedirs
from collections import namedtuple
from base64 import urlsafe_b64encode

import wagon.utils
from flask import Flask
from flask_restful import abort
from flask_security import Security

from manager_rest import config
from manager_rest.constants import ALL_ROLES, ADMIN_ROLE


CLOUDIFY_AUTH_HEADER = 'Authorization'
CLOUDIFY_AUTH_TOKEN_HEADER = 'Authentication-Token'
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
    return os.path.join(config.instance.file_server_uploaded_plugins_folder,
                        plugin_id,
                        archive_name)


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

    Note that when called with an instance object (owner_self, which will be
    set to None if called from the class level), __get__ is applied to the
    instance instead of the class. This is for cases where different behavior
    is expected from instances and classes
    """
    def __init__(self, get_func):
        self.get_func = get_func

    def __get__(self, owner_self, owner_cls):
        if owner_self:
            return self.get_func(owner_self)
        else:
            return self.get_func(owner_cls)


def create_auth_header(username=None, password=None, token=None):
    """Create a valid authentication header either from username/password or
    a token if any were provided; return an empty dict otherwise
    """
    header = {}
    if username and password:
        credentials = '{0}:{1}'.format(username, password)
        header = {CLOUDIFY_AUTH_HEADER:
                  BASIC_AUTH_PREFIX + urlsafe_b64encode(credentials)}
    elif token:
        header = {CLOUDIFY_AUTH_TOKEN_HEADER: token}

    return header


def create_security_roles_and_admin_user(user_datastore,
                                         admin_username,
                                         admin_password,
                                         default_tenant):
    """
    Create security roles and an admin user
    """
    for role in ALL_ROLES:
        user_datastore.create_role(name=role)

    admin_role = user_datastore.find_role(ADMIN_ROLE)
    user_obj = user_datastore.create_user(
        username=admin_username,
        password=admin_password,
        roles=[admin_role]
    )
    user_obj.tenants.append(default_tenant)
    user_datastore.commit()


def setup_flask_app(db, user_datastore, manager_ip='localhost', driver=''):
    """Setup a functioning flask app, when working outside the rest-service

    :param db: An SQLAlchemy object
    :param user_datastore: An SQLAlchemy datastore object
    :param manager_ip: The IP of the manager
    :param driver: SQLA driver for postgres (e.g. pg8000)
    :return: A Flask app
    """
    app = Flask(__name__)
    db_uri = get_postgres_db_uri(manager_ip, driver)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECURITY_USER_IDENTITY_ATTRIBUTES'] = 'username, email'
    Security(app=app, datastore=user_datastore)
    db.init_app(app)
    app.app_context().push()
    return app


def get_postgres_db_uri(manager_ip, driver):
    """Get a valid SQLA DB URI
    """
    dialect = 'postgres+{0}'.format(driver) if driver else 'postgres'
    conf = get_postgres_conf()
    return '{dialect}://{username}:{password}@{host}/{db_name}'.format(
        dialect=dialect,
        username=conf.username,
        password=conf.password,
        host=manager_ip,
        db_name=conf.db_name
    )


def get_postgres_conf():
    """Return a namedtuple with info used to connect to cloudify's PG DB
    """
    conf = namedtuple('PGConf', 'username password db_name')
    return conf(
        username='cloudify',
        password='cloudify',
        db_name='cloudify_db'
    )

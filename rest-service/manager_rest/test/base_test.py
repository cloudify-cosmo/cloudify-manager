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

import unittest
import json
import urllib
import urllib2
import tempfile
import time
import os
import shutil

from flask.testing import FlaskClient
from nose.tools import nottest
from nose.plugins.attrib import attr
from wagon.wagon import Wagon

from manager_rest.storage.models import Tenant
from manager_rest import utils, config, archiving
from manager_rest.storage import FileServer, get_storage_manager
from manager_rest.security.user_handler import add_user_to_tenant
from manager_rest.test.security_utils import get_admin_user, get_admin_role
from manager_rest.test.mocks import MockHTTPClient, CLIENT_API_VERSION, \
    build_query_string
from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.executions import Execution


FILE_SERVER_PORT = 53229
FILE_SERVER_BLUEPRINTS_FOLDER = 'blueprints'
FILE_SERVER_SNAPSHOTS_FOLDER = 'snapshots'
FILE_SERVER_DEPLOYMENTS_FOLDER = 'deployments'
FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER = 'uploaded-blueprints'
FILE_SERVER_RESOURCES_URI = '/resources'
LATEST_API_VERSION = 3  # to be used by max_client_version test attribute
DEFAULT_TENANT_NAME = 'default_tenant'


@nottest
def test_config(**kwargs):
    """
    decorator-generator that can be used on test functions to set
    key-value pairs that may later be injected into functions using the
    "inject_test_config" decorator
    :param kwargs: key-value pairs to be stored on the function object
    :return: a decorator for a test function, which stores with the test's
     config on the test function's object under the "test_config" attribute
    """
    def _test_config_decorator(test_func):
        test_func.test_config = kwargs
        return test_func
    return _test_config_decorator


@nottest
def inject_test_config(f):
    """
    decorator for injecting "test_config" into a test obj method.
    also see the "test_config" decorator
    :param f: a test obj method to be injected with the "test_config" parameter
    :return: the method augmented with the "test_config" parameter
    """
    def _wrapper(test_obj, *args, **kwargs):
        test_func = getattr(test_obj, test_obj.id().split('.')[-1])
        if hasattr(test_func, 'test_config'):
            kwargs['test_config'] = test_func.test_config
        return f(test_obj, *args, **kwargs)
    return _wrapper


class TestClient(FlaskClient):
    """A helper class that overrides flask's default testing.FlaskClient
    class for the purpose of adding authorization headers to all rest calls
    """
    def open(self, *args, **kwargs):
        kwargs = kwargs or {}
        kwargs['headers'] = kwargs.get('headers') or {}
        kwargs['headers'].update(utils.create_auth_header(
            username='admin', password='admin'))
        kwargs['headers']['tenant'] = DEFAULT_TENANT_NAME
        return super(TestClient, self).open(*args, **kwargs)


@attr(client_min_version=1, client_max_version=LATEST_API_VERSION)
class BaseServerTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(BaseServerTestCase, self).__init__(*args, **kwargs)

    def create_client(self, headers=None):
        client = CloudifyClient(host='localhost',
                                headers=headers)
        mock_http_client = MockHTTPClient(self.app,
                                          headers=headers,
                                          file_server=self.file_server)
        client._client = mock_http_client
        client.blueprints.api = mock_http_client
        client.deployments.api = mock_http_client
        client.deployments.outputs.api = mock_http_client
        client.deployment_modifications.api = mock_http_client
        client.executions.api = mock_http_client
        client.nodes.api = mock_http_client
        client.node_instances.api = mock_http_client
        client.manager.api = mock_http_client
        client.evaluate.api = mock_http_client
        client.tokens.api = mock_http_client
        client.events.api = mock_http_client
        # only exists in v2 and above
        if CLIENT_API_VERSION != 'v1':
            client.plugins.api = mock_http_client
            client.snapshots.api = mock_http_client

            # only exists in v2.1 and above
            if CLIENT_API_VERSION != 'v2':
                client.maintenance_mode.api = mock_http_client
                client.deployment_updates.api = mock_http_client

        return client

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='fileserver-')
        fd, self.rest_service_log = tempfile.mkstemp(prefix='rest-log-')
        os.close(fd)
        fd, self.sqlite_db_file = tempfile.mkstemp(prefix='sqlite-db-')
        os.close(fd)
        self.file_server = FileServer(self.tmpdir)
        self.maintenance_mode_dir = tempfile.mkdtemp(prefix='maintenance-')

        self.addCleanup(self.cleanup)
        self.file_server.start()

        # workaround for setting the rest service log path, since it's
        # needed when 'server' module is imported.
        # right after the import the log path is set normally like the rest
        # of the variables (used in the reset_state)
        fd, self.tmp_conf_file = tempfile.mkstemp(prefix='conf-file-')
        os.close(fd)
        with open(self.tmp_conf_file, 'w') as f:
            json.dump({'rest_service_log_path': self.rest_service_log,
                       'rest_service_log_file_size_MB': 1,
                       'rest_service_log_files_backup_count': 1,
                       'rest_service_log_level': 'DEBUG'},
                      f)
        os.environ['MANAGER_REST_CONFIG_PATH'] = self.tmp_conf_file
        try:
            from manager_rest import server
        finally:
            del(os.environ['MANAGER_REST_CONFIG_PATH'])

        self.server_configuration = self.create_configuration()
        server.SQL_DIALECT = 'sqlite'
        server.reset_app(self.server_configuration)
        utils.copy_resources(config.instance.file_server_root)

        self._flask_app_context = server.app.test_request_context()
        self._flask_app_context.push()
        self.addCleanup(self._flask_app_context.pop)

        self.app = self._get_app(server.app)
        self.client = self.create_client()
        server.db.create_all()
        self._init_default_tenant(server.db, server.app)
        self._add_users_and_roles(server.user_datastore)
        self.sm = get_storage_manager()
        self.initialize_provider_context()

    @staticmethod
    def _init_default_tenant(db, app):
        default_tenant = 'default_tenant'
        t = Tenant(name=default_tenant)
        db.session.add(t)
        db.session.commit()

        app.config['tenant'] = t

    @staticmethod
    def _get_app(flask_app):
        """Create a flask.testing FlaskClient

        :param flask_app: Flask app
        """
        flask_app.test_client_class = TestClient
        return flask_app.test_client()

    def _add_users_and_roles(self, user_datastore):
        """Add users and roles for the test

        :param user_datastore: SQLAlchemyDataUserstore
        """
        # Add a fictitious admin user to the user_datastore
        utils.add_users_and_roles_to_userstore(
            user_datastore,
            self._get_users(),
            self._get_roles()
        )

        # Associate all users with the default tenant
        for user in self._get_users():
            add_user_to_tenant(user['username'], DEFAULT_TENANT_NAME)

    @staticmethod
    def _get_users():
        return get_admin_user()

    @staticmethod
    def _get_roles():
        return get_admin_role()

    def cleanup(self):
        self.quiet_delete(self.rest_service_log)
        self.quiet_delete(self.sqlite_db_file)
        self.quiet_delete_directory(self.maintenance_mode_dir)
        if self.file_server:
            self.file_server.stop()
        self.quiet_delete_directory(self.tmpdir)

    def initialize_provider_context(self):
        self.sm.put_provider_context(
            {'name': self.id(), 'context': {'cloudify': {}}}
        )

    def create_configuration(self):
        test_config = config.Config()
        test_config.test_mode = True
        test_config.postgresql_db_name = self.sqlite_db_file
        test_config.postgresql_host = ''
        test_config.postgresql_username = ''
        test_config.postgresql_password = ''
        test_config.file_server_root = self.tmpdir
        test_config.file_server_base_uri = 'http://localhost:{0}'.format(
            FILE_SERVER_PORT)
        test_config.file_server_blueprints_folder = \
            FILE_SERVER_BLUEPRINTS_FOLDER
        test_config.file_server_deployments_folder = \
            FILE_SERVER_DEPLOYMENTS_FOLDER
        test_config.file_server_uploaded_blueprints_folder = \
            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER
        test_config.file_server_snapshots_folder = \
            FILE_SERVER_SNAPSHOTS_FOLDER
        test_config.file_server_resources_uri = FILE_SERVER_RESOURCES_URI
        test_config.rest_service_log_level = 'DEBUG'
        test_config.rest_service_log_path = self.rest_service_log
        test_config.rest_service_log_file_size_MB = 100,
        test_config.rest_service_log_files_backup_count = 20
        test_config.maintenance_folder = self.maintenance_mode_dir
        return test_config

    def _version_url(self, url):
        # method for versionifying URLs for requests which don't go through
        # the REST client; the version is taken from the REST client regardless
        if CLIENT_API_VERSION not in url:
            url = '/api/{0}{1}'.format(CLIENT_API_VERSION, url)

        return url

    def post(self, resource_path, data, query_params=None):
        url = self._version_url(resource_path)
        result = self.app.post(urllib.quote(url),
                               content_type='application/json',
                               data=json.dumps(data),
                               query_string=build_query_string(query_params))
        result.json = json.loads(result.data)
        return result

    def post_file(self, resource_path, file_path, query_params=None):
        url = self._version_url(resource_path)
        with open(file_path) as f:
            result = self.app.post(urllib.quote(url),
                                   data=f.read(),
                                   query_string=build_query_string(
                                       query_params))
            result.json = json.loads(result.data)
            return result

    def put_file(self, resource_path, file_path, query_params=None):
        url = self._version_url(resource_path)
        with open(file_path) as f:
            result = self.app.put(urllib.quote(url),
                                  data=f.read(),
                                  query_string=build_query_string(
                                      query_params))
            result.json = json.loads(result.data)
            return result

    def put(self, resource_path, data=None, query_params=None):
        url = self._version_url(resource_path)
        result = self.app.put(urllib.quote(url),
                              content_type='application/json',
                              data=json.dumps(data) if data else None,
                              query_string=build_query_string(query_params))
        result.json = json.loads(result.data)
        return result

    def patch(self, resource_path, data):
        url = self._version_url(resource_path)
        result = self.app.patch(urllib.quote(url),
                                content_type='application/json',
                                data=json.dumps(data))
        result.json = json.loads(result.data)
        return result

    def get(self, resource_path, query_params=None, headers=None):
        url = self._version_url(resource_path)
        result = self.app.get(urllib.quote(url),
                              headers=headers,
                              query_string=build_query_string(query_params))
        result.json = json.loads(result.data)
        return result

    def head(self, resource_path):
        url = self._version_url(resource_path)
        result = self.app.head(urllib.quote(url))
        return result

    def delete(self, resource_path, query_params=None):
        url = self._version_url(resource_path)
        result = self.app.delete(urllib.quote(url),
                                 query_string=build_query_string(query_params))
        result.json = json.loads(result.data)
        return result

    def _check_if_resource_on_fileserver(self,
                                         folder,
                                         container_id,
                                         resource_path):
        url = 'http://localhost:{0}/{1}/{2}/{3}'.format(
            FILE_SERVER_PORT, folder, container_id, resource_path)
        try:
            urllib2.urlopen(url)
            return True
        except urllib2.HTTPError:
            return False

    def check_if_resource_on_fileserver(self, blueprint_id, resource_path):
        return self._check_if_resource_on_fileserver(
            FILE_SERVER_BLUEPRINTS_FOLDER, blueprint_id, resource_path)

    def get_blueprint_path(self, blueprint_dir_name):
        return os.path.join(os.path.dirname(
            os.path.abspath(__file__)), blueprint_dir_name)

    def archive_mock_blueprint(self, archive_func=archiving.make_targzfile,
                               blueprint_dir='mock_blueprint'):
        archive_path = tempfile.mkstemp()[1]
        source_dir = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), blueprint_dir)
        archive_func(archive_path, source_dir)
        return archive_path

    def get_mock_blueprint_path(self):
        return os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'mock_blueprint', 'blueprint.yaml')

    def put_blueprint_args(self, blueprint_file_name=None,
                           blueprint_id='blueprint',
                           archive_func=archiving.make_targzfile,
                           blueprint_dir='mock_blueprint'):

        resource_path = self._version_url(
            '/blueprints/{1}'.format(CLIENT_API_VERSION, blueprint_id))

        result = [
            resource_path,
            self.archive_mock_blueprint(archive_func, blueprint_dir),
        ]

        if blueprint_file_name:
            data = {'application_file_name': blueprint_file_name}
        else:
            data = {}

        result.append(data)
        return result

    def put_deployment(self,
                       deployment_id='deployment',
                       blueprint_file_name=None,
                       blueprint_id='blueprint',
                       inputs=None,
                       blueprint_dir='mock_blueprint'):
        blueprint_response = self.put_file(
            *self.put_blueprint_args(blueprint_file_name,
                                     blueprint_id,
                                     blueprint_dir=blueprint_dir)).json

        if 'error_code' in blueprint_response:
            raise RuntimeError(
                '{}: {}'.format(blueprint_response['error_code'],
                                blueprint_response['message']))

        blueprint_id = blueprint_response['id']
        deployment = self.client.deployments.create(blueprint_id,
                                                    deployment_id,
                                                    inputs=inputs)
        return blueprint_id, deployment.id, blueprint_response, deployment

    def upload_plugin(self, package_name, package_version):
        temp_file_path = self.create_wheel(package_name, package_version)
        response = self.post_file('/plugins', temp_file_path)
        os.remove(temp_file_path)
        return response

    def create_wheel(self, package_name, package_version):
        module_src = '{0}=={1}'.format(package_name, package_version)
        wagon_client = Wagon(module_src)
        return wagon_client.create(
            archive_destination_dir=tempfile.gettempdir(), force=True)

    def wait_for_url(self, url, timeout=5):
        end = time.time() + timeout

        while end >= time.time():
            try:
                status = urllib.urlopen(url).getcode()
                if status == 200:
                    return
            except IOError:
                time.sleep(1)

        raise RuntimeError('Url {0} is not available (waited {1} '
                           'seconds)'.format(url, timeout))

    @staticmethod
    def quiet_delete(file_path):
        try:
            os.remove(file_path)
        except:
            pass

    @staticmethod
    def quiet_delete_directory(file_path):
        shutil.rmtree(file_path, ignore_errors=True)

    def wait_for_deployment_creation(self, client, deployment_id):
        env_creation_execution = None
        deployment_executions = client.executions.list(deployment_id)
        for execution in deployment_executions:
            if execution.workflow_id == 'create_deployment_environment':
                env_creation_execution = execution
                break
        if env_creation_execution:
            self.wait_for_execution(client, env_creation_execution)

    @staticmethod
    def wait_for_execution(client, execution, timeout=900):
        # Poll for execution status until execution ends
        deadline = time.time() + timeout
        while True:
            if time.time() > deadline:
                raise Exception(
                    'execution of operation {0} for deployment {1} timed out'.
                    format(execution.workflow_id, execution.deployment_id))

            execution = client.executions.get(execution.id)
            if execution.status in Execution.END_STATES:
                break
            time.sleep(3)

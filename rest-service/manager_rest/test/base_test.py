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
import uuid
import os
import shutil

from flask.testing import FlaskClient
from nose.plugins.attrib import attr
from wagon.wagon import Wagon
from mock import MagicMock

from manager_rest import utils, config, constants, archiving
from manager_rest.test.security_utils import get_admin_user
from manager_rest.storage.models_states import ExecutionState
from manager_rest.storage import FileServer, get_storage_manager, models
from manager_rest.storage.storage_utils import \
    create_default_user_tenant_and_roles
from manager_rest.constants import (CLOUDIFY_TENANT_HEADER,
                                    DEFAULT_TENANT_NAME,
                                    FILE_SERVER_BLUEPRINTS_FOLDER)

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError

from .mocks import MockHTTPClient, CLIENT_API_VERSION, build_query_string


FILE_SERVER_PORT = 53229
LATEST_API_VERSION = 3  # to be used by max_client_version test attribute


class TestClient(FlaskClient):
    """A helper class that overrides flask's default testing.FlaskClient
    class for the purpose of adding authorization headers to all rest calls
    """
    def open(self, *args, **kwargs):
        kwargs = kwargs or {}
        admin = get_admin_user()
        kwargs['headers'] = kwargs.get('headers') or {}
        kwargs['headers'].update(utils.create_auth_header(
            username=admin['username'], password=admin['password']))
        kwargs['headers'].setdefault(constants.CLOUDIFY_TENANT_HEADER,
                                     constants.DEFAULT_TENANT_NAME)
        return super(TestClient, self).open(*args, **kwargs)


@attr(client_min_version=1, client_max_version=LATEST_API_VERSION)
class BaseServerTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(BaseServerTestCase, self).__init__(*args, **kwargs)

    def create_client_with_tenant(self,
                                  username,
                                  password,
                                  tenant=DEFAULT_TENANT_NAME):
        headers = utils.create_auth_header(username=username,
                                           password=password)

        headers[CLOUDIFY_TENANT_HEADER] = tenant
        return self.create_client(headers=headers)

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

                # only exists in v3 and above
                if CLIENT_API_VERSION != 'v2.1':
                    client.tenants.api = mock_http_client
                    client.user_groups.api = mock_http_client
                    client.users.api = mock_http_client
                    client.ldap.api = mock_http_client
                    client.secrets.api = mock_http_client

        return client

    def setUp(self):
        self._create_temp_files_and_folders()
        self._init_file_server()

        server_module = self._set_config_path_and_get_server_module()
        self._create_config_and_reset_app(server_module)
        self._handle_flask_app_and_db(server_module)
        self.client = self.create_client()
        self.sm = get_storage_manager()
        self.initialize_provider_context()

    def _create_temp_files_and_folders(self):
        self.tmpdir = tempfile.mkdtemp(prefix='fileserver-')
        fd, self.rest_service_log = tempfile.mkstemp(prefix='rest-log-')
        os.close(fd)
        self.maintenance_mode_dir = tempfile.mkdtemp(prefix='maintenance-')
        fd, self.tmp_conf_file = tempfile.mkstemp(prefix='conf-file-')
        os.close(fd)

    def _init_file_server(self):
        self.file_server = FileServer(self.tmpdir)
        self.file_server.start()
        self.addCleanup(self.cleanup)

    def _set_config_path_and_get_server_module(self):
        """Workaround for setting the rest service log path, since it's
        needed when 'server' module is imported.
        right after the import the log path is set normally like the rest
        of the variables (used in the reset_state)
        """

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
        return server

    def _create_config_and_reset_app(self, server):
        """Create config, and reset Flask app
        :type server: module
        """
        self.server_configuration = self.create_configuration()
        utils.copy_resources(self.server_configuration.file_server_root)
        server.SQL_DIALECT = 'sqlite'
        server.reset_app(self.server_configuration)

    def _handle_flask_app_and_db(self, server):
        """Set up Flask app context, and handle DB related tasks
        :type server: module
        """
        self._set_flask_app_context(server.app)
        self.app = self._get_app(server.app)
        self._handle_default_db_config(server)
        self._setup_anonymous_user(server.app, server.user_datastore)

    def _set_flask_app_context(self, flask_app):
        flask_app_context = flask_app.test_request_context()
        flask_app_context.push()
        self.addCleanup(flask_app_context.pop)

    def _handle_default_db_config(self, server):
        server.db.create_all()
        admin_user = get_admin_user()
        default_tenant = create_default_user_tenant_and_roles(
            admin_username=admin_user['username'],
            admin_password=admin_user['password'],
        )
        server.app.config[constants.CURRENT_TENANT_CONFIG] = default_tenant

    @staticmethod
    def _get_app(flask_app):
        """Create a flask.testing FlaskClient

        :param flask_app: Flask app
        :return: Our modified version of Flask's test client
        """
        flask_app.test_client_class = TestClient
        return flask_app.test_client()

    @staticmethod
    def _setup_anonymous_user(flask_app, user_datastore):
        """Change the anonymous user to be admin, in order to have arbitrary
        access to the storage manager (which otherwise requires a valid user)

        :param flask_app: Flask app
        """
        admin_user = user_datastore.get_user(get_admin_user()['username'])
        login_manager = flask_app.extensions['security'].login_manager
        login_manager.anonymous_user = MagicMock(return_value=admin_user)

    def cleanup(self):
        self.quiet_delete(self.rest_service_log)
        self.quiet_delete(self.tmp_conf_file)
        self.quiet_delete_directory(self.maintenance_mode_dir)
        if self.file_server:
            self.file_server.stop()
        self.quiet_delete_directory(self.tmpdir)

    def initialize_provider_context(self):
        provider_context = models.ProviderContext(
            id=constants.PROVIDER_CONTEXT_ID,
            name=self.id(),
            context={'cloudify': {}}
        )
        self.sm.put(provider_context)

    def create_configuration(self):
        test_config = config.Config()
        test_config.test_mode = True
        test_config.postgresql_db_name = ':memory:'
        test_config.postgresql_host = ''
        test_config.postgresql_username = ''
        test_config.postgresql_password = ''
        test_config.file_server_root = self.tmpdir
        test_config.file_server_url = 'http://localhost:{0}'.format(
            self.file_server.port)

        test_config.rest_service_log_level = 'DEBUG'
        test_config.rest_service_log_path = self.rest_service_log
        test_config.rest_service_log_file_size_MB = 100,
        test_config.rest_service_log_files_backup_count = 20
        test_config.maintenance_folder = self.maintenance_mode_dir
        test_config.security_hash_salt = 'hash_salt'
        test_config.security_secret_key = 'secret_key'
        test_config.security_encoding_alphabet = \
            'L7SMZ4XebsuIK8F6aVUBYGQtW0P12Rn'
        test_config.security_encoding_block_size = 24
        test_config.security_encoding_min_length = 5
        return test_config

    def _version_url(self, url):
        # method for versionifying URLs for requests which don't go through
        # the REST client; the version is taken from the REST client regardless
        if not url.startswith('/api/'):
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
            os.path.join(FILE_SERVER_BLUEPRINTS_FOLDER, DEFAULT_TENANT_NAME),
            blueprint_id, resource_path)

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
            if execution.status in ExecutionState.END_STATES:
                break
            time.sleep(3)

    def _add_blueprint(self, blueprint_id=None):
        if not blueprint_id:
            unique_str = str(uuid.uuid4())
            blueprint_id = 'blueprint-{0}'.format(unique_str)
        now = utils.get_formatted_timestamp()
        blueprint = models.Blueprint(id=blueprint_id,
                                     created_at=now,
                                     updated_at=now,
                                     description=None,
                                     plan={'name': 'my-bp'},
                                     main_file_name='aaa')
        return self.sm.put(blueprint)

    def _add_deployment(self, blueprint, deployment_id=None):
        if not deployment_id:
            unique_str = str(uuid.uuid4())
            deployment_id = 'deployment-{0}'.format(unique_str)
        now = utils.get_formatted_timestamp()
        deployment = models.Deployment(id=deployment_id,
                                       created_at=now,
                                       updated_at=now,
                                       permalink=None,
                                       description=None,
                                       workflows={},
                                       inputs={},
                                       policy_types={},
                                       policy_triggers={},
                                       groups={},
                                       scaling_groups={},
                                       outputs={})
        deployment.blueprint = blueprint
        return self.sm.put(deployment)

    def _add_execution_with_id(self, execution_id):
        blueprint = self._add_blueprint()
        deployment = self._add_deployment(blueprint.id)
        return self._add_execution(deployment.id, execution_id)

    def _add_execution(self, deployment, execution_id=None):
        if not execution_id:
            unique_str = str(uuid.uuid4())
            execution_id = 'execution-{0}'.format(unique_str)
        execution = models.Execution(
            id=execution_id,
            status=ExecutionState.TERMINATED,
            workflow_id='',
            created_at=utils.get_formatted_timestamp(),
            error='',
            parameters=dict(),
            is_system_workflow=False)
        execution.deployment = deployment
        return self.sm.put(execution)

    def _add_deployment_update(self, deployment, execution,
                               deployment_update_id=None):
        if not deployment_update_id:
            unique_str = str(uuid.uuid4())
            deployment_update_id = 'deployment_update-{0}'.format(unique_str)
        now = utils.get_formatted_timestamp()
        deployment_update = models.DeploymentUpdate(
            deployment_plan={'name': 'my-bp'},
            state='staged',
            id=deployment_update_id,
            deployment_update_nodes=None,
            deployment_update_node_instances=None,
            deployment_update_deployment=None,
            modified_entity_ids=None,
            created_at=now)
        deployment_update.deployment = deployment
        if execution:
            deployment_update.execution = execution
        return self.sm.put(deployment_update)

    def _test_invalid_input(self, func, argument, *args):
        self.assertRaisesRegexp(
            CloudifyClientError,
            'The `{0}` argument contains illegal characters'.format(argument),
            func,
            *args
        )

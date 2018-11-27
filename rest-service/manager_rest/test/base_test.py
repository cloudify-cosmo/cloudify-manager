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
import json
import time
import uuid
import urllib
import shutil
import zipfile
import urllib2
import tarfile
import unittest
import tempfile

import yaml
import wagon

from mock import MagicMock, patch
from flask.testing import FlaskClient

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify.models_states import ExecutionState, VisibilityState

from manager_rest import server
from manager_rest.rest import rest_utils
from manager_rest.test.attribute import attr
from manager_rest.flask_utils import set_admin_current_user
from manager_rest.test.security_utils import get_admin_user
from manager_rest import utils, config, constants, archiving
from manager_rest.storage import FileServer, get_storage_manager, models
from manager_rest.storage.storage_utils import \
    create_default_user_tenant_and_roles
from manager_rest.constants import (CLOUDIFY_TENANT_HEADER,
                                    DEFAULT_TENANT_NAME,
                                    FILE_SERVER_BLUEPRINTS_FOLDER)

from .mocks import (
    MockHTTPClient,
    CLIENT_API_VERSION,
    build_query_string,
    mock_execute_task
)


FILE_SERVER_PORT = 53229
LATEST_API_VERSION = 3.1  # to be used by max_client_version test attribute

permitted_roles = ['sys_admin', 'manager', 'user', 'operations', 'viewer']
auth_dict = {
    'roles': [
        {'name': 'sys_admin', 'description': ''},
        {'name': 'manager', 'description': ''},
        {'name': 'user', 'description': ''},
        {'name': 'viewer', 'description': ''},
        {'name': 'default', 'description': ''}
    ],
    'permissions': {
        'all_tenants': ['sys_admin', 'manager'],
        'administrators': ['sys_admin', 'manager'],
        'tenant_rabbitmq_credentials': ['sys_admin', 'manager'],
        'create_global_resource': ['sys_admin'],
        'execute_global_workflow': ['sys_admin', 'manager'],
        'execution_list': permitted_roles,
        'deployment_list': permitted_roles,
        'blueprint_list': permitted_roles
    }
}


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
        kwargs['headers'][constants.CLOUDIFY_TENANT_HEADER] = \
            constants.DEFAULT_TENANT_NAME
        return super(TestClient, self).open(*args, **kwargs)


@attr(client_min_version=1, client_max_version=LATEST_API_VERSION)
class BaseServerTestCase(unittest.TestCase):
    @classmethod
    def create_client_with_tenant(cls,
                                  username,
                                  password,
                                  tenant=DEFAULT_TENANT_NAME):
        headers = utils.create_auth_header(username=username,
                                           password=password)

        headers[CLOUDIFY_TENANT_HEADER] = tenant
        return cls.create_client(headers=headers)

    @classmethod
    def create_client(cls, headers=None):
        client = CloudifyClient(host='localhost',
                                headers=headers)
        mock_http_client = MockHTTPClient(cls.app,
                                          headers=headers,
                                          file_server=cls.file_server)
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

                    # only exists in v3.1 and above
                    if CLIENT_API_VERSION != 'v3':
                        client.deployments.capabilities.api = mock_http_client
                        client.agents.api = mock_http_client

        return client

    @classmethod
    def setUpClass(cls):
        super(BaseServerTestCase, cls).setUpClass()

        cls._patchers = []
        cls._create_temp_files_and_folders()
        cls._init_file_server()
        cls._mock_amqp_modules()
        cls._mock_swagger()

        cls._create_config_and_reset_app()
        cls._mock_get_encryption_key()
        cls._handle_flask_app_and_db()
        cls.client = cls.create_client()
        cls.sm = get_storage_manager()
        cls._mock_verify_role()

        for patcher in cls._patchers:
            patcher.start()

    def setUp(self):
        self._handle_default_db_config()
        self.initialize_provider_context()
        self._setup_current_user()

    def tearDown(self):
        self._drop_db(['roles'])

    @staticmethod
    def _drop_db(keep_tables):
        """Creates a single transaction that *always* drops all tables, regardless
        of relationships and foreign key constraints (as opposed to `db.drop_all`)
        """
        meta = server.db.metadata
        for table in reversed(meta.sorted_tables):
            if table.name in keep_tables:
                continue
            server.db.session.execute(table.delete())
        server.db.session.commit()

    @classmethod
    def _mock_verify_role(cls):
        cls._original_verify_role = rest_utils.verify_role
        rest_utils.verify_role = MagicMock()

    @classmethod
    def _mock_swagger(cls):
        """ We don't need swagger for tests, so might as well mock it """

        swagger_patcher = patch(
            'manager_rest.rest.swagger.add_swagger_resource'
        )
        cls._patchers.append(swagger_patcher)

    @classmethod
    def _mock_amqp_modules(cls):
        """
        Mock RabbitMQ related modules - AMQP manager and workflow executor -
        that use pika, because we don't have RabbitMQ in the unittests
        """
        amqp_patches = [
            patch('manager_rest.amqp_manager.RabbitMQClient'),
            patch('manager_rest.workflow_executor._execute_task',
                  mock_execute_task),
        ]
        cls._patchers.extend(amqp_patches)

    @classmethod
    def _mock_get_encryption_key(cls):
        """ Mock the _get_encryption_key_patcher function for all unittests """
        get_encryption_key_patcher = patch(
            'cloudify.cryptography_utils._get_encryption_key',
            MagicMock(return_value=config.instance.security_encryption_key)
        )
        cls._patchers.append(get_encryption_key_patcher)

    @classmethod
    def _create_temp_files_and_folders(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix='fileserver-')
        fd, cls.rest_service_log = tempfile.mkstemp(prefix='rest-log-')
        os.close(fd)
        cls.maintenance_mode_dir = tempfile.mkdtemp(prefix='maintenance-')
        fd, cls.tmp_conf_file = tempfile.mkstemp(prefix='conf-file-')
        os.close(fd)

    @classmethod
    def _init_file_server(cls):
        cls.file_server = FileServer(cls.tmpdir)
        cls.file_server.start()

    @classmethod
    def _create_config_and_reset_app(cls):
        """Create config, and reset Flask app
        """
        cls.server_configuration = cls.create_configuration()
        utils.copy_resources(cls.server_configuration.file_server_root)
        server.SQL_DIALECT = 'sqlite'
        server.reset_app(cls.server_configuration)

        cls._set_hash_mechanism_to_plaintext()

    @staticmethod
    def _set_hash_mechanism_to_plaintext():
        """
        Hashing is the most time consuming task we perform during unittesets,
        so we will not encrypt user passwords during tests, as this should
        be tested elsewhere more in depth
        """
        security = server.app.extensions['security']
        security.password_hash = 'plaintext'
        record = security.pwd_context._config._records[('plaintext', None)]
        security.pwd_context._config._records[(None, None)] = record



    @classmethod
    def _handle_flask_app_and_db(cls):
        """Set up Flask app context, and handle DB related tasks
        """
        cls._set_flask_app_context()
        cls.app = cls._get_app(server.app)

    @classmethod
    def _set_flask_app_context(cls):
        flask_app_context = server.app.test_request_context()
        flask_app_context.push()

    @staticmethod
    def _handle_default_db_config():
        server.db.create_all()
        admin_user = get_admin_user()

        fd, temp_auth_file = tempfile.mkstemp()
        os.close(fd)
        with open(temp_auth_file, 'w') as f:
            yaml.dump(auth_dict, f)

        try:
            # We're mocking the AMQPManager, we aren't really using Rabbit here
            default_tenant = create_default_user_tenant_and_roles(
                admin_username=admin_user['username'],
                admin_password=admin_user['password'],
                amqp_manager=MagicMock(),
                authorization_file_path=temp_auth_file
            )
            default_tenant.rabbitmq_password = \
                'gAAAAABb9p7U_Lnlmg7vyijjoxovyg215ThYi-VCTCzVYa1p-vpzi31WGko' \
                'KD_hK1mQyKgjRss_Nz-3m-cgHpZChnVT4bxZIjnOnL6sF8RtozvlRoGHtnF' \
                'G6jxqQDeEf5Heos0ia4Q5H  '
        finally:
            os.remove(temp_auth_file)

        utils.set_current_tenant(default_tenant)

    @staticmethod
    def _get_app(flask_app):
        """Create a flask.testing FlaskClient

        :param flask_app: Flask app
        :return: Our modified version of Flask's test client
        """
        flask_app.test_client_class = TestClient
        return flask_app.test_client()

    @staticmethod
    def _setup_current_user():
        """Change the anonymous user to be admin, in order to have arbitrary
        access to the storage manager (which otherwise requires a valid user)
        """
        admin_user = set_admin_current_user(server.app)
        login_manager = server.app.extensions['security'].login_manager
        login_manager.anonymous_user = MagicMock(return_value=admin_user)

    @classmethod
    def tearDownClass(cls):
        cls.quiet_delete(cls.rest_service_log)
        cls.quiet_delete(cls.tmp_conf_file)
        cls.quiet_delete_directory(cls.maintenance_mode_dir)
        cls.quiet_delete_directory(cls.tmpdir)

        if cls.file_server:
            cls.file_server.stop()

        for patcher in cls._patchers:
            patcher.start()

    @classmethod
    def initialize_provider_context(cls):
        provider_context = models.ProviderContext(
            id=constants.PROVIDER_CONTEXT_ID,
            name=cls.__name__,
            context={'cloudify': {}}
        )
        cls.sm.put(provider_context)

    @classmethod
    def create_configuration(cls):
        test_config = config.Config()
        test_config.test_mode = True
        test_config.postgresql_db_name = ':memory:'
        test_config.postgresql_host = ''
        test_config.postgresql_username = ''
        test_config.postgresql_password = ''
        test_config.file_server_root = cls.tmpdir
        test_config.file_server_url = 'http://localhost:{0}'.format(
            cls.file_server.port)

        test_config.rest_service_log_level = 'DEBUG'
        test_config.rest_service_log_path = self.rest_service_log
        test_config.rest_service_log_file_size_MB = 100,
        test_config.rest_service_log_files_backup_count = 7
        test_config.maintenance_folder = cls.maintenance_mode_dir
        test_config.security_hash_salt = 'hash_salt'
        test_config.security_secret_key = 'secret_key'
        test_config.security_encoding_alphabet = \
            'L7SMZ4XebsuIK8F6aVUBYGQtW0P12Rn'
        test_config.security_encoding_block_size = 24
        test_config.security_encoding_min_length = 5
        test_config.authorization_permissions = auth_dict['permissions']
        test_config.security_encryption_key = (
            'lF88UP5SJKluylJIkPDYrw5UMKOgv9w8TikS0Ds8m2UmM'
            'SzFe0qMRa0EcTgHst6LjmF_tZbq_gi_VArepMsrmw=='
        )
        return test_config

    @staticmethod
    def _version_url(url):
        # method for versionifying URLs for requests which don't go through
        # the REST client; the version is taken from the REST client regardless
        if not url.startswith('/api/'):
            url = '/api/{0}{1}'.format(CLIENT_API_VERSION, url)

        return url

    # this method is completely copied from the cli. once caravan sits in a
    # more general package, it should be removed.
    @staticmethod
    def _create_caravan(mappings, dest, name=None):
        tempdir = tempfile.mkdtemp()
        metadata = {}

        for wgn_path, yaml_path in mappings.iteritems():
            plugin_root_dir = os.path.basename(wgn_path).split('.', 1)[0]
            os.mkdir(os.path.join(tempdir, plugin_root_dir))

            dest_wgn_path = os.path.join(plugin_root_dir,
                                         os.path.basename(wgn_path))
            dest_yaml_path = os.path.join(plugin_root_dir,
                                          os.path.basename(yaml_path))

            shutil.copy(wgn_path, os.path.join(tempdir, dest_wgn_path))
            shutil.copy(yaml_path, os.path.join(tempdir, dest_yaml_path))
            metadata[dest_wgn_path] = dest_yaml_path

        with open(os.path.join(tempdir, 'METADATA'), 'w+') as f:
            yaml.dump(metadata, f)

        tar_name = name or 'palace'
        tar_path = os.path.join(dest, '{0}.cvn'.format(tar_name))
        tarfile_ = tarfile.open(tar_path, 'w:gz')
        try:
            tarfile_.add(tempdir, arcname=tar_name)
        finally:
            tarfile_.close()
        return tar_path

    def post(self, resource_path, data, query_params=None):
        url = self._version_url(resource_path)
        result = self.app.post(urllib.quote(url),
                               content_type='application/json',
                               data=json.dumps(data),
                               query_string=build_query_string(query_params))
        return result

    @classmethod
    def post_file(cls, resource_path, file_path, query_params=None):
        url = cls._version_url(resource_path)
        with open(file_path) as f:
            result = cls.app.post(urllib.quote(url),
                                  data=f.read(),
                                  query_string=build_query_string(
                                      query_params))
            return result

    def put_file(self, resource_path, file_path, query_params=None):
        url = self._version_url(resource_path)
        with open(file_path) as f:
            result = self.app.put(urllib.quote(url),
                                  data=f.read(),
                                  query_string=build_query_string(
                                      query_params))
            return result

    def put(self, resource_path, data=None, query_params=None):
        url = self._version_url(resource_path)
        result = self.app.put(urllib.quote(url),
                              content_type='application/json',
                              data=json.dumps(data) if data else None,
                              query_string=build_query_string(query_params))
        return result

    def patch(self, resource_path, data):
        url = self._version_url(resource_path)
        result = self.app.patch(urllib.quote(url),
                                content_type='application/json',
                                data=json.dumps(data))
        return result

    def get(self, resource_path, query_params=None, headers=None):
        url = self._version_url(resource_path)
        result = self.app.get(urllib.quote(url),
                              headers=headers,
                              query_string=build_query_string(query_params))
        return result

    def head(self, resource_path):
        url = self._version_url(resource_path)
        result = self.app.head(urllib.quote(url))
        return result

    def delete(self, resource_path, query_params=None):
        url = self._version_url(resource_path)
        result = self.app.delete(urllib.quote(url),
                                 query_string=build_query_string(query_params))
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

    @staticmethod
    def get_full_path(relative_file_path):
        return os.path.join(os.path.dirname(
            os.path.abspath(__file__)), relative_file_path)

    def upload_blueprint(self,
                         client,
                         visibility=VisibilityState.TENANT,
                         blueprint_id='bp_1'):
        bp_path = self.get_blueprint_path('mock_blueprint/blueprint.yaml')
        client.blueprints.upload(path=bp_path,
                                 entity_id=blueprint_id,
                                 visibility=visibility)
        return blueprint_id

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
                       blueprint_dir='mock_blueprint',
                       skip_plugins_validation=None):
        blueprint_response = self.put_blueprint(blueprint_dir,
                                                blueprint_file_name,
                                                blueprint_id)
        blueprint_id = blueprint_response['id']
        create_deployment_kwargs = {'inputs': inputs}
        if skip_plugins_validation is not None:
            create_deployment_kwargs['skip_plugins_validation'] =\
                skip_plugins_validation
        deployment = self.client.deployments.create(blueprint_id,
                                                    deployment_id,
                                                    **create_deployment_kwargs)
        return blueprint_id, deployment.id, blueprint_response, deployment

    def put_blueprint(self, blueprint_dir, blueprint_file_name, blueprint_id):
        blueprint_response = self.put_file(
            *self.put_blueprint_args(blueprint_file_name,
                                     blueprint_id,
                                     blueprint_dir=blueprint_dir)).json
        if 'error_code' in blueprint_response:
            raise RuntimeError(
                '{}: {}'.format(blueprint_response['error_code'],
                                blueprint_response['message']))
        return blueprint_response

    @staticmethod
    def _create_wagon_and_yaml(package_name,
                               package_version,
                               package_yaml_file='mock_blueprint/plugin.yaml'):
        temp_file_path = BaseServerTestCase.create_wheel(package_name,
                                                         package_version)
        yaml_path = BaseServerTestCase.get_full_path(package_yaml_file)
        return temp_file_path, yaml_path

    @classmethod
    def upload_plugin(cls,
                      package_name,
                      package_version,
                      package_yaml='mock_blueprint/plugin.yaml'):
        wgn_path, yaml_path = cls._create_wagon_and_yaml(
            package_name,
            package_version,
            package_yaml
        )
        zip_path = cls.zip_files([wgn_path, yaml_path])
        response = cls.post_file('/plugins', zip_path)
        os.remove(wgn_path)
        return response

    @staticmethod
    def zip_files(files):
        source_folder = tempfile.mkdtemp()
        destination_zip = source_folder + '.zip'
        for path in files:
            shutil.copy(path, source_folder)
        BaseServerTestCase.zip(source_folder, destination_zip,
                               include_folder=False)
        return destination_zip

    @staticmethod
    def zip(source, destination, include_folder=True):
        with zipfile.ZipFile(destination, 'w') as zip_file:
            for root, _, files in os.walk(source):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    source_dir = os.path.dirname(source) if include_folder \
                        else source
                    zip_file.write(
                        file_path, os.path.relpath(file_path, source_dir))
        return destination

    @staticmethod
    def create_wheel(package_name, package_version):
        module_src = '{0}=={1}'.format(package_name, package_version)
        return wagon.create(
            module_src,
            archive_destination_dir=tempfile.gettempdir(),
            force=True
        )

    def upload_caravan(self, packages):
        mapping = dict(
            self._create_wagon_and_yaml(
                package,
                version_and_yaml[0],
                version_and_yaml[1])
            for package, version_and_yaml in packages.items()
        )

        caravan_path = self._create_caravan(mapping, tempfile.gettempdir())
        response = self.post_file('/plugins', caravan_path)
        os.remove(caravan_path)
        return response

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
        except Exception:
            pass

    @staticmethod
    def quiet_delete_directory(file_path):
        shutil.rmtree(file_path, ignore_errors=True)

    def wait_for_deployment_creation(self, client, deployment_id):
        env_creation_execution = None
        deployment_executions = client.executions.list(
            deployment_id=deployment_id
        )
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

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
import shutil
import logging
import zipfile
import tarfile
import unittest
import tempfile
import sqlalchemy.exc
from sqlalchemy.orm.session import close_all_sessions

import yaml
import wagon
import psycopg2
import requests
import traceback

from flask_migrate import Migrate, upgrade
from mock import MagicMock, patch
from flask.testing import FlaskClient
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify._compat import urlquote
from cloudify.models_states import (ExecutionState,
                                    VisibilityState,
                                    BlueprintUploadState)
from cloudify.constants import CLOUDIFY_EXECUTION_TOKEN_HEADER
from cloudify.cluster_status import (
    DB_STATUS_REPORTER,
    BROKER_STATUS_REPORTER,
    MANAGER_STATUS_REPORTER,
)

from manager_rest import server
from manager_rest.rest import rest_utils
from manager_rest.storage.models_base import db
from manager_rest.rest.filters_utils import FilterRule
from manager_rest.resource_manager import get_resource_manager
from manager_rest.flask_utils import set_admin_current_user
from manager_rest.storage.filters import add_filter_rules_to_query
from manager_rest.test.security_utils import (get_admin_user,
                                              get_status_reporters)
from manager_rest import utils, config, constants, archiving
from manager_rest.storage import get_storage_manager, models
from manager_rest.storage.storage_utils import (
    create_default_user_tenant_and_roles,
    create_status_reporter_user_and_assign_role
)
from manager_rest.constants import (
    AttrsOperator,
    LabelsOperator,
    DEFAULT_TENANT_NAME,
    CLOUDIFY_TENANT_HEADER,
    CONVENTION_APPLICATION_BLUEPRINT_FILE,
)
from manager_rest import premium_enabled

from .mocks import (
    MockHTTPClient,
    CLIENT_API_VERSION,
    build_query_string,
    mock_send_mgmtworker_task,
    upload_mock_cloudify_license
)


MIGRATION_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'resources', 'rest-service',
    'cloudify', 'migrations'
))

permitted_roles = ['sys_admin', 'manager', 'user', 'operations', 'viewer']
auth_dict = {
    'roles': [
        {'name': 'sys_admin', 'description': ''},
        {'name': MANAGER_STATUS_REPORTER, 'description': ''},
        {'name': BROKER_STATUS_REPORTER, 'description': ''},
        {'name': DB_STATUS_REPORTER, 'description': ''},
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
        'broker_credentials': ['sys_admin', 'manager'],
        'execution_list': permitted_roles,
        'deployment_list': permitted_roles,
        'blueprint_list': permitted_roles,
        'secret_create': ['sys_admin', 'manager', 'user'],
        'maintenance_mode_set': ['sys_admin']
    }
}


class TestClient(FlaskClient):
    """A helper class that overrides flask's default testing.FlaskClient
    class for the purpose of adding authorization headers to all rest calls
    """
    def __init__(self, *args, **kwargs):
        self._user = kwargs.pop('user')
        super(TestClient, self).__init__(*args, **kwargs)

    def open(self, *args, **kwargs):
        kwargs = kwargs or {}
        kwargs['headers'] = kwargs.get('headers') or {}
        if CLOUDIFY_EXECUTION_TOKEN_HEADER not in kwargs['headers']:
            kwargs['headers'].update(
                utils.create_auth_header(
                    username=self._user['username'],
                    password=self._user['password']
                )
            )
        kwargs['headers'].setdefault(
            constants.CLOUDIFY_TENANT_HEADER,
            constants.DEFAULT_TENANT_NAME
        )
        return super(TestClient, self).open(*args, **kwargs)


class BaseServerTestCase(unittest.TestCase):
    # hack for running tests with py2's unnitest, but using py3's
    # assert method name; to be removed once we run unittests on py3 only
    LABELS = [{'env': 'aws'}, {'arch': 'k8s'}]
    LABELS_2 = [{'env': 'gcp'}, {'arch': 'k8s'}]
    FILTER_ID = 'filter'
    FILTER_RULES = [
        FilterRule('env', ['aws'], LabelsOperator.NOT_ANY_OF, 'label'),
        FilterRule('arch', ['k8s'], LabelsOperator.ANY_OF, 'label'),
        FilterRule('created_by', ['admin'], AttrsOperator.ANY_OF, 'attribute'),
    ]

    FILTER_RULES_2 = [
        FilterRule('env', ['aws'], LabelsOperator.ANY_OF, 'label'),
        FilterRule('arch', ['k8s'], LabelsOperator.ANY_OF, 'label'),
        FilterRule('created_by', ['admin'], AttrsOperator.ANY_OF, 'attribute'),
    ]

    def assertEmpty(self, obj):
        self.assertIsNotNone(obj)
        self.assertFalse(obj)

    def assert_metadata_filtered(self, resource_list, filtered_cnt):
        self.assertEqual(resource_list.metadata.get('filtered'), filtered_cnt)

    def assert_resource_labels(self, resource_labels, compared_labels):
        simplified_labels = set()
        compared_labels_set = set()

        for label in resource_labels:
            simplified_labels.add((label['key'], label['value']))

        for compared_label in compared_labels:
            [(key, value)] = compared_label.items()
            compared_labels_set.add((key, value))

        self.assertEqual(simplified_labels, compared_labels_set)

    @staticmethod
    def assert_filters_applied(filter_rules_params, resource_ids_set,
                               resource_model=models.Deployment):
        """Asserts the right resources return when filter rules are applied

        :param filter_rules_params: List of filter rules parameters
        :param resource_ids_set: The corresponding deployments' IDs set
        :param resource_model: The resource model to filter.
               Can be Deployment or Blueprint
        """
        filter_rules = [FilterRule(*params) for params in filter_rules_params]
        query = db.session.query(resource_model)
        query = add_filter_rules_to_query(query, resource_model, filter_rules)
        results = query.all()

        assert resource_ids_set == set(res.id for res in results)

    @classmethod
    def create_client_with_tenant(cls,
                                  username,
                                  password,
                                  tenant=DEFAULT_TENANT_NAME):
        app = cls._get_app(server.app, user={
            'username': username,
            'password': password
        })
        headers = {CLOUDIFY_TENANT_HEADER: tenant}
        return cls.create_client(headers=headers, app=app)

    @classmethod
    def create_client(cls, headers=None, app=None):
        if app is None:
            app = cls.app
        client = CloudifyClient(host='localhost',
                                headers=headers)
        mock_http_client = MockHTTPClient(
            app, headers=headers, root_path=cls.tmpdir)
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
                        client.tasks_graphs.api = mock_http_client
                        client.operations.api = mock_http_client
                        client.plugins_update.api = mock_http_client
                        client.sites.api = mock_http_client
                        client.inter_deployment_dependencies.api = \
                            mock_http_client
                        client.deployments_labels.api = mock_http_client
                        client.blueprints_filters.api = mock_http_client
                        client.deployments_filters.api = mock_http_client
                        client.deployment_groups.api = mock_http_client
                        client.execution_groups.api = mock_http_client
                        client.execution_schedules.api = mock_http_client
                        client.blueprints_labels.api = mock_http_client
                        client.workflows.api = mock_http_client

        return client

    @classmethod
    def setUpClass(cls):
        super(BaseServerTestCase, cls).setUpClass()

        cls._patchers = []
        cls._create_temp_files_and_folders()
        cls._mock_amqp_modules()
        cls._mock_swagger()

        cls._create_config_and_reset_app()
        cls._mock_get_encryption_key()
        cls._handle_flask_app_and_db()
        cls.client = cls.create_client()
        cls.sm = get_storage_manager()
        cls.rm = get_resource_manager()
        cls._mock_verify_role()

        for patcher in cls._patchers:
            patcher.start()

    def setUp(self):
        self._handle_default_db_config()
        self.initialize_provider_context()
        self._setup_current_user()
        self.addCleanup(self._drop_db, keep_tables=['config'])
        self.addCleanup(self._clean_tmpdir)
        self.user = db.session.query(models.User).first()
        self.tenant = db.session.query(models.Tenant).first()

    @staticmethod
    def _drop_db(keep_tables=None):
        """Creates a single transaction that clears all tables by deleting
        their contents, which is faster than dropping and recreating
        the tables.
        """
        close_all_sessions()
        if keep_tables is None:
            keep_tables = []
        meta = server.db.metadata
        for table in reversed(meta.sorted_tables):
            if table.name in keep_tables:
                continue
            server.db.session.execute(table.delete())
        server.db.session.commit()
        db.engine.dispose()

    def _clean_tmpdir(self):
        shutil.rmtree(os.path.join(self.tmpdir, 'blueprints'),
                      ignore_errors=True)
        shutil.rmtree(os.path.join(self.tmpdir, 'uploaded-blueprints'),
                      ignore_errors=True)

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
            patch('manager_rest.workflow_executor._send_mgmtworker_task',
                  mock_send_mgmtworker_task),
            patch('manager_rest.workflow_executor._broadcast_mgmtworker_task'),
            patch('manager_rest.workflow_executor.execute_workflow',
                  mock_send_mgmtworker_task),
            patch('manager_rest.resource_manager.send_event'),
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
        cls.tmpdir = tempfile.mkdtemp()
        fd, cls.rest_service_log = tempfile.mkstemp(prefix='rest-log-')
        os.close(fd)
        cls.maintenance_mode_dir = tempfile.mkdtemp(prefix='maintenance-')
        fd, cls.tmp_conf_file = tempfile.mkstemp(prefix='conf-file-')
        os.close(fd)

    @classmethod
    def _create_config_and_reset_app(cls):
        """Create config, and reset Flask app
        """
        cls.server_configuration = cls.create_configuration()
        utils.copy_resources(cls.server_configuration.file_server_root)
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
        security.hashing_schemes = ['plaintext']
        record = security.pwd_context._config._records[('plaintext', None)]
        security.pwd_context._config._records[(None, None)] = record
        security.hashing_context._config._records[(None, None)] = record
        security.hashing_context._config._records[('plaintext', None)] = record
        security.hashing_context._config.schemes = ('plaintext',)

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
    def _insert_default_permissions():
        sess = server.db.session
        for role in auth_dict['roles']:
            sess.add(models.Role(type='system_role', **role))
        roles = {r.name: r.id for r in sess.query(models.Role)}
        for perm, perm_roles in auth_dict['permissions'].items():
            for role_name in perm_roles:
                if role_name not in roles:
                    continue
                sess.add(models.Permission(
                    role_id=roles[role_name],
                    name=perm))
        sess.commit()

    @staticmethod
    def _handle_default_db_config():
        Migrate(app=server.app, db=server.db)
        try:
            upgrade(directory=MIGRATION_DIR)
        except sqlalchemy.exc.OperationalError:
            logger = logging.getLogger()
            logger.error("Could not connect to the database - is a "
                         "postgresql server running on localhost?")
            logger.error("HINT: Create a docker container running postgresql "
                         "by doing `docker run --name cloudify-db-unit-test "
                         "-e POSTGRES_PASSWORD=cloudify -e POSTGRES_USER="
                         "cloudify -e POSTGRES_DB=cloudify_db -p 5432:5432 "
                         "-d postgres`")
            raise
        admin_user = get_admin_user()

        BaseServerTestCase._insert_default_permissions()
        # We're mocking the AMQPManager, we aren't really using Rabbit here
        default_tenant = create_default_user_tenant_and_roles(
            admin_username=admin_user['username'],
            admin_password=admin_user['password'],
            amqp_manager=MagicMock()
        )
        default_tenant.rabbitmq_username = \
            'rabbitmq_username_default_tenant'
        default_tenant.rabbitmq_vhost = \
            'rabbitmq_vhost_defualt_tenant'
        default_tenant.rabbitmq_password = \
            'gAAAAABb9p7U_Lnlmg7vyijjoxovyg215ThYi-VCTCzVYa1p-vpzi31WGko' \
            'KD_hK1mQyKgjRss_Nz-3m-cgHpZChnVT4bxZIjnOnL6sF8RtozvlRoGHtnF' \
            'G6jxqQDeEf5Heos0ia4Q5H  '

        for reporter in get_status_reporters():
            create_status_reporter_user_and_assign_role(
                reporter['username'],
                reporter['password'],
                reporter['role'],
                reporter['id']
            )
        if premium_enabled:
            # License is required only when working with Cloudify Premium
            upload_mock_cloudify_license(get_storage_manager())

        utils.set_current_tenant(default_tenant)

    @staticmethod
    def _get_app(flask_app, user=None):
        """Create a flask.testing FlaskClient

        :param flask_app: Flask app
        :param user: a dict containing username and password
        :return: Our modified version of Flask's test client
        """
        if user is None:
            user = get_admin_user()
        flask_app.test_client_class = TestClient
        return flask_app.test_client(user=user)

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

        for patcher in cls._patchers:
            patcher.stop()

    @classmethod
    def initialize_provider_context(cls):
        provider_context = models.ProviderContext(
            id=constants.PROVIDER_CONTEXT_ID,
            name=cls.__name__,
            context={'cloudify': {}}
        )
        cls.sm.put(provider_context)

    @classmethod
    def _db_exists(cls, test_config, dbname):
        if os.environ.get('DB_EXISTS') == dbname:
            return True
        try:
            conn = psycopg2.connect(
                host=test_config.postgresql_host,
                user=test_config.postgresql_username,
                password=test_config.postgresql_password,
                dbname=dbname)
        except psycopg2.OperationalError as e:
            if 'does not exist' in str(e):
                return False
            raise
        else:
            conn.close()
        return True

    @classmethod
    def _create_db(cls, test_config, dbname):
        conn = psycopg2.connect(
            host=test_config.postgresql_host,
            user=test_config.postgresql_username,
            password=test_config.postgresql_password,
            dbname='cloudify_db')
        try:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                cur.execute(f'CREATE DATABASE {dbname}')
        finally:
            conn.close()
        os.environ['DB_EXISTS'] = dbname

    @classmethod
    def _find_db_name(cls, test_config):
        """Figure out the db name to use.

        By default, use cloudify_db. But if we're running under pytest-xdist,
        magically create more databases to run on! Each process gets its own.
        With pytest-xdist, the workers are named gw0, gw1, gw2, etc.
        The first one gets to use cloudify_db, all other ones create more
        databases.
        """
        dbname = 'cloudify_db'
        worker_id = os.environ.get('PYTEST_XDIST_WORKER')
        if worker_id and worker_id != 'gw0':
            dbname += '_' + worker_id
            if not cls._db_exists(test_config, dbname):
                cls._create_db(test_config, dbname)
        return dbname

    @classmethod
    def create_configuration(cls):
        test_config = config.Config()
        test_config.can_load_from_db = False

        test_config.test_mode = True
        test_config.postgresql_host = 'localhost'
        test_config.postgresql_username = 'cloudify'
        test_config.postgresql_password = 'cloudify'
        test_config.postgresql_connection_options = {
            'connect_timeout': 2
        }
        test_config.postgresql_db_name = cls._find_db_name(test_config)
        test_config.file_server_root = cls.tmpdir
        test_config.file_server_url = 'http://localhost:53229'

        test_config.rest_service_log_level = 'INFO'
        test_config.rest_service_log_path = cls.rest_service_log
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
        test_config.authorization_roles = []
        test_config.security_encryption_key = (
            'lF88UP5SJKluylJIkPDYrw5UMKOgv9w8TikS0Ds8m2UmM'
            'SzFe0qMRa0EcTgHst6LjmF_tZbq_gi_VArepMsrmw=='
        )

        test_config.amqp_host = 'localhost'
        test_config.amqp_username = 'guest'
        test_config.amqp_password = 'guest'
        test_config.amqp_ca_path = None
        test_config.amqp_management_host = 'localhost'
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

        for wgn_path, yaml_path in mappings.items():
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
        result = self.app.post(urlquote(url),
                               content_type='application/json',
                               data=json.dumps(data),
                               query_string=build_query_string(query_params))
        return result

    @classmethod
    def post_file(cls, resource_path, file_path, query_params=None):
        url = cls._version_url(resource_path)
        with open(file_path, 'rb') as f:
            result = cls.app.post(urlquote(url),
                                  data=f.read(),
                                  query_string=build_query_string(
                                      query_params))
            return result

    def put_file(self, resource_path, file_path, query_params=None):
        url = self._version_url(resource_path)
        with open(file_path, 'rb') as f:
            result = self.app.put(urlquote(url),
                                  data=f.read(),
                                  query_string=build_query_string(
                                      query_params))
            return result

    def put(self, resource_path, data=None, query_params=None):
        url = self._version_url(resource_path)
        result = self.app.put(urlquote(url),
                              content_type='application/json',
                              data=json.dumps(data) if data else None,
                              query_string=build_query_string(query_params))
        return result

    def patch(self, resource_path, data):
        url = self._version_url(resource_path)
        result = self.app.patch(urlquote(url),
                                content_type='application/json',
                                data=json.dumps(data))
        return result

    def get(self, resource_path, query_params=None, headers=None):
        url = self._version_url(resource_path)
        result = self.app.get(urlquote(url),
                              headers=headers,
                              query_string=build_query_string(query_params))
        return result

    def head(self, resource_path):
        url = self._version_url(resource_path)
        result = self.app.head(urlquote(url))
        return result

    def delete(self, resource_path, query_params=None):
        url = self._version_url(resource_path)
        result = self.app.delete(urlquote(url),
                                 query_string=build_query_string(query_params))
        return result

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
                                 visibility=visibility,
                                 async_upload=True)
        self.execute_upload_blueprint_workflow(blueprint_id, client)
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
            '/blueprints/{0}'.format(blueprint_id))

        result = [
            resource_path,
            self.archive_mock_blueprint(archive_func, blueprint_dir),
        ]

        if blueprint_file_name:
            data = {'application_file_name': blueprint_file_name}
        else:
            data = {}
        data['async_upload'] = True
        result.append(data)
        return result

    def put_deployment(self,
                       deployment_id='deployment',
                       blueprint_file_name=None,
                       blueprint_id='blueprint',
                       inputs=None,
                       blueprint_dir='mock_blueprint',
                       skip_plugins_validation=None,
                       site_name=None,
                       labels=None,
                       client=None,
                       dep_visibility=None,
                       bp_visibility=VisibilityState.TENANT,
                       display_name=None):
        client = client or self.client
        blueprint_response = self.put_blueprint(blueprint_dir,
                                                blueprint_file_name,
                                                blueprint_id,
                                                client=client,
                                                visibility=bp_visibility)
        blueprint_id = blueprint_response['id']
        create_deployment_kwargs = {'inputs': inputs}
        if site_name:
            create_deployment_kwargs['site_name'] = site_name
        if labels:
            create_deployment_kwargs['labels'] = labels
        if skip_plugins_validation is not None:
            create_deployment_kwargs['skip_plugins_validation'] =\
                skip_plugins_validation
        if dep_visibility:
            create_deployment_kwargs['visibility'] = dep_visibility
        if display_name:
            create_deployment_kwargs['display_name'] = display_name
        deployment = client.deployments.create(blueprint_id,
                                               deployment_id,
                                               **create_deployment_kwargs)
        self.create_deployment_environment(deployment, client=client)
        deployment = client.deployments.get(deployment_id)
        return blueprint_id, deployment.id, blueprint_response, deployment

    def create_deployment_environment(self, deployment, client=None):
        from cloudify_system_workflows.deployment_environment import create
        client = client or self.client
        m = MagicMock()
        deployment = self.sm.get(models.Deployment, deployment.id)
        blueprint = client.blueprints.get(deployment.blueprint_id)
        m.deployment = client.deployments.get(deployment.id)
        m.blueprint = blueprint
        m.tenant_name = deployment.tenant_name
        deployment.create_execution.status = ExecutionState.STARTED
        self.sm.update(deployment.create_execution)
        get_rest_client_target = \
            'cloudify_system_workflows.deployment_environment.get_rest_client'
        with patch(get_rest_client_target, return_value=client), \
                patch('cloudify_system_workflows.deployment_environment.'
                      'os.makedirs'):
            try:
                create(m, **deployment.create_execution.parameters)
            except Exception:
                client.executions.update(
                    deployment.create_execution.id, ExecutionState.FAILED)
                raise
            else:
                client.executions.update(
                    deployment.create_execution.id, ExecutionState.TERMINATED)

    def delete_deployment(self, deployment_id):
        """Delete the deployment from the database.

        Delete via the resource manager, because otherwise deleting
        deployments requires rabbitmq, which these tests don't have.
        """
        self.rm.delete_deployment(
            self.sm.get(models.Deployment, deployment_id))

    def put_blueprint(self,
                      blueprint_dir='mock_blueprint',
                      blueprint_file_name=None,
                      blueprint_id='blueprint',
                      client=None,
                      labels=None,
                      visibility=VisibilityState.TENANT):
        client = client or self.client
        if not blueprint_file_name:
            blueprint_file_name = CONVENTION_APPLICATION_BLUEPRINT_FILE

        blueprint_path = self.get_blueprint_path(
            os.path.join(blueprint_dir, blueprint_file_name))
        client.blueprints.upload(path=blueprint_path,
                                 entity_id=blueprint_id,
                                 async_upload=True,
                                 labels=labels,
                                 visibility=visibility)
        self.execute_upload_blueprint_workflow(blueprint_id, client)
        blueprint = client.blueprints.get(blueprint_id)
        return blueprint

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
            archive_destination_dir=tempfile.mkdtemp(),
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
                if requests.get(url).status_code == 200:
                    return
            except requests.exceptions.RequestException:
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

    def execute_upload_blueprint_workflow(self, blueprint_id, client=None):
        from cloudify_system_workflows.blueprint import upload
        client = client or self.client
        blueprint = self.sm.get(models.Blueprint, blueprint_id)
        executions = self.sm.list(models.Execution,
                                  filters={'workflow_id': 'upload_blueprint'})
        for exec in executions:
            uploaded_blueprint_id = exec.parameters.get('blueprint_id')
            if uploaded_blueprint_id and uploaded_blueprint_id == blueprint_id:
                uploaded_blueprint_execution = exec
                break
        else:
            raise Exception(f'No `upload_blueprint` execution was found for '
                            f'the blueprint {blueprint_id}')

        m = MagicMock()
        with patch('cloudify_system_workflows.blueprint.get_rest_client',
                   return_value=client):
            try:
                upload(m, **uploaded_blueprint_execution.parameters)
            except Exception as e:
                blueprint.state = BlueprintUploadState.FAILED_UPLOADING
                blueprint.error = str(e)
                blueprint.error_traceback = traceback.format_exc()
                self.sm.update(blueprint)
                raise

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
                                       display_name=deployment_id,
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

    def _add_execution(self, deployment, execution_id=None, workflow_id=''):
        if not execution_id:
            unique_str = str(uuid.uuid4())
            execution_id = 'execution-{0}'.format(unique_str)
        execution = models.Execution(
            id=execution_id,
            status=ExecutionState.TERMINATED,
            workflow_id=workflow_id,
            created_at=utils.get_formatted_timestamp(),
            error='',
            parameters=dict(),
            is_system_workflow=False,
            blueprint_id=deployment.blueprint_id
        )
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
        self.assertRaisesRegex(
            CloudifyClientError,
            'The `{0}` argument contains illegal characters'.format(argument),
            func,
            *args
        )

    def put_deployment_with_labels(self, labels, resource_id=None,
                                   client=None, blueprint_file_name=None,
                                   **deployment_kwargs):
        client = client or self.client
        resource_id = resource_id or 'i{0}'.format(uuid.uuid4())
        blueprint_file_name = blueprint_file_name or 'blueprint.yaml'
        _, _, _, deployment = self.put_deployment(
            blueprint_file_name=blueprint_file_name,
            blueprint_id=resource_id,
            deployment_id=resource_id,
            labels=labels,
            client=client,
            **deployment_kwargs)

        return deployment

    def put_blueprint_with_labels(self, labels, resource_id=None,
                                  **blueprint_kwargs):
        if resource_id:
            blueprint_kwargs['blueprint_id'] = resource_id

        return self.put_blueprint(labels=labels, **blueprint_kwargs)

    @staticmethod
    def create_filter(filters_client, filter_id, filter_rules,
                      visibility=VisibilityState.TENANT):
        return filters_client.create(filter_id, filter_rules, visibility)

    @staticmethod
    def _get_filter_rules_by_type(filter_rules, filter_rules_type):
        return [filter_rule for filter_rule in filter_rules if
                filter_rule['type'] == filter_rules_type]

    def get_new_user_with_role(self, username, password, role,
                               tenant=DEFAULT_TENANT_NAME):
        self.client.users.create(username, password, role='default')
        self.client.tenants.add_user(username, tenant, role=role)
        return self.create_client_with_tenant(username, password)

    def _put_mock_blueprint(self):
        blueprint_id = str(uuid.uuid4())
        now = utils.get_formatted_timestamp()
        return self.sm.put(
            models.Blueprint(
                id=blueprint_id,
                created_at=now,
                updated_at=now,
                main_file_name='abcd',
                plan={})
        )

    @staticmethod
    def _get_mock_deployment(deployment_id, blueprint):
        now = utils.get_formatted_timestamp()
        deployment = models.Deployment(
            id=deployment_id,
            display_name=deployment_id,
            created_at=now,
            updated_at=now,
        )
        deployment.blueprint = blueprint
        return deployment

    def put_mock_deployments(self, source_deployment, target_deployment):
        blueprint = self._put_mock_blueprint()
        source_deployment = self._get_mock_deployment(source_deployment,
                                                      blueprint)
        self.sm.put(source_deployment)
        target_deployment = self._get_mock_deployment(target_deployment,
                                                      blueprint)
        self.sm.put(target_deployment)

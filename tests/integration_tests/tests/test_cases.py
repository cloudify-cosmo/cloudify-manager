########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import json
import time
import uuid
import yaml
import shutil
import tarfile
import logging
import datetime
import tempfile
import unittest
from contextlib import contextmanager

import wagon
from pytest import mark
from retrying import retry
import requests
from zipfile import ZipFile
from requests.exceptions import ConnectionError

import cloudify.logs
import cloudify.utils
import cloudify.event
from cloudify.snapshots import STATES, SNAPSHOT_RESTORE_FLAG_FILE

from logging.handlers import RotatingFileHandler

from manager_rest.utils import mkdirs
from manager_rest.constants import CLOUDIFY_TENANT_HEADER

from integration_tests.framework import utils, hello_world, docl, env
from integration_tests.framework.flask_utils import reset_storage, \
    prepare_reset_storage_script
from integration_tests.tests import utils as test_utils
from integration_tests.framework.constants import (PLUGIN_STORAGE_DIR,
                                                   CLOUDIFY_USER)
from integration_tests.framework.wagon_build import (WagonBuilderMixin,
                                                     WagonBuildError)
from integration_tests.tests.utils import (
    wait_for_deployment_creation_to_complete,
    wait_for_deployment_deletion_to_complete
)

from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import CloudifyClientError


class BaseTestCase(unittest.TestCase):
    """
    A test case for cloudify integration tests.
    """

    @classmethod
    def setUpClass(cls):
        env.create_env(cls.environment_type)
        BaseTestCase.env = env.instance

    @classmethod
    def tearDownClass(cls):
        env.destroy_env()

    def setUp(self):
        self.workdir = tempfile.mkdtemp(
            dir=self.env.test_working_dir,
            prefix='{0}-'.format(self._testMethodName))
        self.cfy = test_utils.get_cfy()
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)
        self._set_tests_framework_logger()
        self.client = None

    @classmethod
    def _update_config(cls, new_config):
        config_file_location = '/opt/manager/cloudify-rest.conf'
        config = yaml.load(cls.read_manager_file(config_file_location))
        config.update(new_config)
        with tempfile.NamedTemporaryFile() as f:
            yaml.dump(config, f)
            f.flush()
            cls.copy_file_to_manager(
                source=f.name,
                target=config_file_location,
                owner=CLOUDIFY_USER
            )
        cls.restart_service('cloudify-restservice')

    def _setup_running_manager_attributes(self):
        self.client = test_utils.create_rest_client()

    def tearDown(self):
        self.env.stop_dispatch_processes()

    def _save_manager_logs_after_test(self, purge=True):
        self.logger.info("Attempting to save the manager's logs...")
        try:
            self._save_manager_logs_after_test_helper(purge)
        except Exception as e:
            self.logger.info(
                "Unable to save logs due to exception: {}".format(str(e)))

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def _save_manager_logs_after_test_helper(self, purge):
        self.logger.debug('_save_manager_logs_after_test started')
        logs_dir = os.environ.get('CFY_LOGS_PATH_REMOTE')
        if not logs_dir:
            self.logger.info("No Cloudify remote log saving path found. You "
                             "can set one up with the OS env "
                             "var CFY_LOGS_PATH_REMOTE")
        else:
            self.logger.info("Cloudify remote log saving path found: [{0}]."
                             .format(logs_dir))
        self.logger.info("If you're running via itest-runner, make sure to "
                         "set a local path as well with CFY_LOGS_PATH_LOCAL.")
        test_path = self.id().split('.')[-2:]
        if not logs_dir:
            self.logger.debug('not saving manager logs')
            return
        if os.environ.get('SKIP_LOG_SAVE_ON_SUCCESS') \
                and sys.exc_info() == (None, None, None):
            self.logger.info('Not saving manager logs for successful test:  '
                             '{0}'.format(test_path[-1]))
            return

        self.logger.info(
            'Saving manager logs for test:  {0}...'.format(test_path[-1]))
        logs_dir = os.path.join(os.path.expanduser(logs_dir), *test_path)
        mkdirs(logs_dir)
        target = os.path.join(logs_dir, 'logs.tar.gz')
        self.cfy.logs.download(output_path=target)
        if purge:
            self.cfy.logs.purge(force=True)

        if not bool(os.environ.get('SKIP_LOGS_EXTRACTION')):
            with tarfile.open(target) as tar:
                self.logger.debug('Extracting tar.gz: {0}'.format(target))
                tar.extractall(path=logs_dir)
                self.logger.debug('Removing {0}'.format(target))
                os.remove(target)

        self.logger.debug('_save_manager_logs_after_test completed')

    @staticmethod
    def _set_file_handler(path):
        mega = 1024 * 1024
        if not os.path.isdir(path):
            raise IOError('dir does not exist')
        path = os.path.join(path, 'integration_tests_framework.log')
        handler = RotatingFileHandler(path, maxBytes=5 * mega, backupCount=5)
        handler.setLevel(logging.DEBUG)
        return handler

    def _set_tests_framework_logger(self):
        handlers = [logging.StreamHandler(sys.stdout)]
        handlers[0].setLevel(logging.INFO)
        logs_path = '/var/log/cloudify'
        try:
            handlers.append(BaseTestCase._set_file_handler(logs_path))
        except IOError:
            self.logger = cloudify.utils.setup_logger(self._testMethodName)
            self.logger.debug('Framework logs are not saved into a file. '
                              'To allow logs saving, make sure the directory '
                              '{0} exists with Permissions to edit.'.format(
                                                                    logs_path))
            return

        self.logger = cloudify.utils.setup_logger(self._testMethodName,
                                                  logging.NOTSET,
                                                  handlers=handlers)
        separator = '\n\n\n' + ('=' * 100)
        self.logger.debug(separator)
        self.logger.debug('Starting test:  {0} on {1}'.format(
            self.id(), datetime.datetime.now()))
        self.logger.info('Framework logs are saved in {0}'.format(logs_path))

    @staticmethod
    def read_manager_file(file_path, no_strip=False):
        """
        Read a file from the cloudify manager filesystem.
        """
        return docl.read_file(file_path, no_strip=no_strip)

    @staticmethod
    def delete_manager_file(file_path, quiet=True):
        """
        Remove file from a cloudify manager
        """
        return docl.execute('rm -rf {0}'.format(file_path), quiet=quiet)

    @staticmethod
    def execute_on_manager(command, quiet=True):
        """
        Execute a shell command on the cloudify manager container.
        """
        return docl.execute(command, quiet)

    @staticmethod
    def clear_directory(dir_path, quiet=True):
        """
        Remove all contents from a directory
        """
        # Add a wildcard to the end, to remove everything *inside* the folder
        command = 'rm -rf {0}/*'.format(dir_path)

        # Need to invoke a shell directly, because `docker exec` ignores
        # wildcards by default
        command = "sh -c '{0}'".format(command)
        return docl.execute(command, quiet)

    @staticmethod
    def copy_file_to_manager(source, target, owner=None):
        """
        Copy a file to the cloudify manager filesystem

        """
        ret_val = docl.copy_file_to_manager(
            source=source, target=target)
        if owner:
            BaseTestCase.env.chown(owner, target)
        return ret_val

    @staticmethod
    def copy_file_from_manager(source, target, owner=None):
        """
        Copy a file to the cloudify manager filesystem

        """
        ret_val = docl.copy_file_from_manager(
            source=source, target=target)
        if owner:
            BaseTestCase.env.chown(owner, target)
        return ret_val

    def write_data_to_file_on_manager(self,
                                      data,
                                      target_path,
                                      to_json=False,
                                      owner=None):
        with tempfile.NamedTemporaryFile() as f:
            if to_json:
                data = json.dumps(data)
            f.write(data)
            f.flush()
            self.copy_file_to_manager(f.name, target_path, owner=owner)

    @staticmethod
    def restart_service(service_name):
        """
        restart service by name in the manager container

        """
        docl.execute('systemctl stop {0}'.format(service_name))
        docl.execute('systemctl start {0}'.format(service_name))

    @staticmethod
    def get_docker_host():
        """
        returns the host IP

        """
        return docl.docker_host()

    def get_plugin_data(self, plugin_name, deployment_id):
        """
        Retrieve the plugin state for a certain deployment.

        :param deployment_id: the deployment id in question.
        :param plugin_name: the plugin in question.
        :return: plugin data relevant for the deployment.
        :rtype dict
        """
        data = self.read_manager_file(
            os.path.join(PLUGIN_STORAGE_DIR, '{0}.json'.format(plugin_name))
        )
        if not data:
            return {}
        data = json.loads(data)
        return data.get(deployment_id, {})

    def clear_plugin_data(self, plugin_name):
        """
        Clears plugin state.

        :param plugin_name: the plugin in question.
        """
        self.delete_manager_file(
            os.path.join(PLUGIN_STORAGE_DIR, '{0}.json'.format(plugin_name))
        )

    @staticmethod
    def do_assertions(assertions_func, timeout=10, **kwargs):
        return test_utils.do_retries(assertions_func,
                                     timeout,
                                     AssertionError,
                                     **kwargs)

    @staticmethod
    def execute_workflow(workflow_name, deployment_id,
                         parameters=None,
                         timeout_seconds=240,
                         wait_for_execution=True,
                         force=False,
                         queue=False,
                         client=None,
                         **kwargs):
        """A blocking method which runs the requested workflow"""
        client = client or test_utils.create_rest_client()
        execution = client.executions.start(deployment_id, workflow_name,
                                            parameters=parameters or {},
                                            force=force, queue=queue, **kwargs)
        if wait_for_execution:
            BaseTestCase.wait_for_execution_to_end(
                execution,
                client=client,
                timeout_seconds=timeout_seconds)
        return execution

    @staticmethod
    def deploy(dsl_path, blueprint_id=None, deployment_id=None,
               inputs=None, wait=True, client=None,
               runtime_only_evaluation=False):
        client = client or test_utils.create_rest_client()
        resource_id = uuid.uuid4()
        blueprint_id = blueprint_id or 'blueprint_{0}'.format(resource_id)
        blueprint = client.blueprints.upload(dsl_path, blueprint_id)
        deployment_id = deployment_id or 'deployment_{0}'.format(resource_id)
        deployment = client.deployments.create(
            blueprint.id,
            deployment_id,
            inputs=inputs,
            skip_plugins_validation=True,
            runtime_only_evaluation=runtime_only_evaluation)
        if wait:
            wait_for_deployment_creation_to_complete(deployment_id,
                                                     client=client)
        return deployment

    @staticmethod
    def deploy_and_execute_workflow(dsl_path,
                                    workflow_name,
                                    timeout_seconds=240,
                                    blueprint_id=None,
                                    deployment_id=None,
                                    wait_for_execution=True,
                                    parameters=None,
                                    inputs=None,
                                    queue=False,
                                    **kwargs):
        """
        A blocking method which deploys an application from
        the provided dsl path, and runs the requested workflows
        """
        deployment = BaseTestCase.deploy(dsl_path,
                                         blueprint_id,
                                         deployment_id,
                                         inputs)
        execution = BaseTestCase.execute_workflow(
                workflow_name, deployment.id, parameters,
                timeout_seconds, wait_for_execution, queue=queue, **kwargs)
        return deployment, execution.id

    @staticmethod
    def deploy_application(dsl_path,
                           timeout_seconds=60,
                           blueprint_id=None,
                           deployment_id=None,
                           wait_for_execution=True,
                           inputs=None,
                           queue=False,
                           **kwargs):
        """
        A blocking method which deploys an application
        from the provided dsl path.
        """
        return BaseTestCase.deploy_and_execute_workflow(
                dsl_path=dsl_path,
                workflow_name='install',
                timeout_seconds=timeout_seconds,
                blueprint_id=blueprint_id,
                deployment_id=deployment_id,
                wait_for_execution=wait_for_execution,
                inputs=inputs,
                queue=queue,
                **kwargs
        )

    @staticmethod
    def undeploy_application(deployment_id,
                             timeout_seconds=240,
                             is_delete_deployment=False,
                             parameters=None):
        """
        A blocking method which undeploys an application from the provided dsl
        path.
        """
        client = test_utils.create_rest_client()
        execution = client.executions.start(deployment_id,
                                            'uninstall',
                                            parameters=parameters)
        BaseTestCase.wait_for_execution_to_end(
                execution,
                timeout_seconds=timeout_seconds)

        if execution.error and execution.error != 'None':
            raise RuntimeError(
                    'Workflow execution failed: {0}'.format(execution.error))
        if is_delete_deployment:
            BaseTestCase.delete_deployment(deployment_id, validate=True)
        return execution.id

    @staticmethod
    def get_manager_ip():
        return utils.get_manager_ip()

    @staticmethod
    def delete_deployment(deployment_id,
                          ignore_live_nodes=False,
                          validate=False,
                          client=None):
        client = client or test_utils.create_rest_client()
        result = client.deployments.delete(deployment_id,
                                           ignore_live_nodes=ignore_live_nodes,
                                           with_logs=True)
        if validate:
            wait_for_deployment_deletion_to_complete(deployment_id,
                                                     client=client)
        return result

    @staticmethod
    def is_node_started(node_id):
        client = test_utils.create_rest_client()
        node_instance = client.node_instances.get(node_id)
        return node_instance['state'] == 'started'

    @staticmethod
    def wait_for_execution_to_end(execution, timeout_seconds=240, client=None):
        if not client:
            client = test_utils.create_rest_client()
        deadline = time.time() + timeout_seconds
        while execution.status not in Execution.END_STATES:
            assert execution.ended_at is None
            time.sleep(0.5)
            execution = client.executions.get(execution.id)
            if time.time() > deadline:
                raise utils.TimeoutException(
                        'Execution timed out: \n{0}'
                        .format(json.dumps(execution, indent=2)))
        if execution.status == Execution.FAILED:
            raise RuntimeError(
                    'Workflow execution failed: {0} [{1}]'.format(
                        execution.error,
                        execution.status))
        return execution

    def wait_for_snapshot_restore_to_end(self,
                                         execution_id=None,
                                         timeout_seconds=480,
                                         client=None):
        def is_client_error(exception):
            return isinstance(exception, CloudifyClientError)

        @retry(retry_on_exception=is_client_error,
               stop_max_attempt_number=3,
               wait_fixed=10000)
        def try_fetch_status():
            status = ''
            while status != STATES.NOT_RUNNING:
                time.sleep(0.5)
                status = client.snapshots.get_status()['status']
                if time.time() > deadline:
                    raise utils.TimeoutException(
                        'Snapshot restore timed out.{0}'
                        ''.format(error_message_suffix))

        client = client or self.client
        error_message_suffix = (
            ' Execution ID provided: {0}'.format(execution_id)
            if execution_id else '')
        deadline = time.time() + timeout_seconds
        self._wait_for_restore_marker_file_to_be_created()
        try_fetch_status()

    def _wait_for_restore_marker_file_to_be_created(self, timeout_seconds=40):
        self.logger.debug("Waiting for snapshot restore marker to be "
                          "created...")
        deadline = time.time() + timeout_seconds
        exists = None
        while not exists:
            time.sleep(0.5)
            exists = self._does_restore_marker_file_exists()
            if time.time() > deadline:
                self.fail("Timed out waiting for the restore marker file to "
                          "be created.")
        self.logger.debug("Snapshot restore marker file created.")
        return True

    def _does_restore_marker_file_exists(self):
        ls_exit_code = self.execute_on_manager(
            "sh -c 'ls {0} &> /dev/null; echo $?'"
            "".format(SNAPSHOT_RESTORE_FLAG_FILE)
        ).stdout.strip()
        return ls_exit_code == '0'

    @contextmanager
    def client_using_tenant(self, client, tenant_name):
        curr_tenant = client._client.headers.get(CLOUDIFY_TENANT_HEADER)
        try:
            client._client.headers[CLOUDIFY_TENANT_HEADER] = tenant_name
            yield
        finally:
            client._client.headers[CLOUDIFY_TENANT_HEADER] = curr_tenant

    def make_file_with_name(self, content, filename, base_dir=None):
        base_dir = (os.path.join(self._temp_dir, base_dir)
                    if base_dir else self.workdir)
        filename_path = os.path.join(base_dir, filename)
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        with open(filename_path, 'w') as f:
            f.write(content)
        return filename_path

    def make_yaml_file(self, content):
        filename = 'tempfile{0}.yaml'.format(uuid.uuid4())
        filename_path = self.make_file_with_name(content, filename)
        return filename_path

    def wait_for_all_executions_to_end(self):
        executions = self.client.executions.list(include_system_workflows=True)
        for execution in executions:
            if execution['status'] not in Execution.END_STATES:
                self.wait_for_execution_to_end(execution)

    def wait_for_event(self, execution, message, timeout_seconds=60,
                       allow_connection_error=True, client=None):
        """ Wait until a specific event is listed in the DB.

        Events are stored asynchronously, so we might need to wait for
        an event to be stored in the database.

        :param execution: Check events for this execution
        :param message: Wait for an event with this message
        :param timeout_seconds: How long to keep polling
        :param allow_connection_error: Catch the exception if a connection
            error happens when polling for events. This is useful for tests
            that also change the db in the meantime (snapshots)
        :param client: The restclient to use
        """
        client = client or self.client
        deadline = time.time() + timeout_seconds
        all_events = []
        while not any(message in e['message'] for e in all_events):
            time.sleep(0.5)
            if time.time() > deadline:
                raise utils.TimeoutException(
                    'Execution timed out when waiting for message {0}: \n{1}'
                    .format(message, json.dumps(execution, indent=2))
                )
            # This might fail due to the fact that we're changing the DB in
            # real time - it's OK. When restoring a snapshot we also restart
            # the rest service and nginx, which might lead to intermittent
            # connection errors. Just try again
            try:
                all_events = client.events.list(
                    execution_id=execution.id, include_logs=True)
            except (CloudifyClientError, ConnectionError):
                if not allow_connection_error:
                    raise


class AgentlessTestCase(BaseTestCase):
    environment_type = env.AgentlessTestEnvironment

    @classmethod
    def setUpClass(cls):
        super(AgentlessTestCase, cls).setUpClass()
        prepare_reset_storage_script()

    def setUp(self):
        super(AgentlessTestCase, self).setUp()
        self._setup_running_manager_attributes()
        reset_storage()
        docl.upload_mock_license()
        self._reset_file_system()
        self.addCleanup(self._save_manager_logs_after_test)

    def _reset_file_system(self):
        """ Clean up any files left on the FS from the previous test """

        self.logger.info('Cleaning up the file system...')

        # Remove everything *inside* the folders
        self.clear_directory('/opt/mgmtworker/work/deployments')
        self.clear_directory('/opt/manager/resources/blueprints')
        self.clear_directory('/opt/manager/resources/uploaded-blueprints')

    def _get_latest_execution(self, workflow_id):
        execution_list = self.client.executions.list(
            include_system_workflows=True,
            sort='created_at',
            is_descending=True,
            workflow_id=workflow_id).items
        self.assertGreater(
            len(execution_list),
            0,
            msg='Expected to find at least one execution with '
                'workflow_id `{workflow_id}`, but found: '
                '{execution_list}'.format(
                workflow_id=workflow_id, execution_list=execution_list)
        )
        return execution_list[0]


class BaseAgentTestCase(BaseTestCase):
    environment_type = env.AgentTestEnvironment

    @classmethod
    def setUpClass(cls):
        super(BaseAgentTestCase, cls).setUpClass()

    def tearDown(self):
        self.logger.info('Removing leftover test containers')
        docl.clean(label=['marker=test', self.env.env_label])
        super(BaseAgentTestCase, self).tearDown()

    def read_host_file(self, file_path, deployment_id, node_id):
        """
        Read a file from a dockercompute node instance container filesystem.
        """
        runtime_props = self._get_runtime_properties(
            deployment_id=deployment_id, node_id=node_id)
        container_id = runtime_props['container_id']
        return docl.read_file(file_path, container_id=container_id)

    def get_host_ip(self, deployment_id, node_id):
        """
        Get the ip of a dockercompute node instance container.
        """
        runtime_props = self._get_runtime_properties(
            deployment_id=deployment_id, node_id=node_id)
        return runtime_props['ip']

    def get_host_key_path(self, deployment_id, node_id):
        """
        Get the the path on the manager container to the private key
        used to SSH into the dockercompute node instance container.
        """
        runtime_props = self._get_runtime_properties(
            deployment_id=deployment_id, node_id=node_id)
        return runtime_props['cloudify_agent']['key']

    def _get_runtime_properties(self, deployment_id, node_id):
        instance = self.client.node_instances.list(
            deployment_id=deployment_id,
            node_id=node_id)[0]
        return instance.runtime_properties

    @mark.skip("Basic test frame to be used in other tests")
    def test_hello_world(self,
                         use_cli=False,
                         modify_blueprint_func=None,
                         skip_uninstall=False):
        """
        Install the hello world example and perform basic assertion that things
        work correctly. This method should be used by tests when a general
        sanity blueprint is required. The main blueprint file used can be found
        at resources/dockercompute_helloworld/blueprint.yaml. It is copied to
        the hello world directory after it is fetched from github.

        The modify_blueprint_func can be used in cases where there is need to
        perform some modification to the base blueprint. The signature of this
        function is (patcher, blueprint_dir) where patcher is a yaml patcher
        that can be used to override the main blueprint file. blueprint dir
        can be used in case the tests needs to modify other files in the the
        blueprint directory.

        :param use_cli: Not implemented yet. Current, installation uses the
                        REST client directly
        :param modify_blueprint_func: Modification function. (see above)
        :param skip_uninstall: Should uninstall be skipped
        :return:
        """
        return hello_world.test_hello_world(
            test_case=self,
            use_cli=use_cli,
            modify_blueprint_func=modify_blueprint_func,
            skip_uninstall=skip_uninstall)

    def _create_secrets(self, secrets):
        self.logger.info('Adding secrets...')
        for key, value in secrets.items():
            self.logger.info('Adding secret {0} {1}...'.format(key, value))
            while not any([secret for secret in
                           self.client.secrets.list()
                           if key in secret.key]):
                self.client.secrets.create(key, value, update_if_exists=True)
                time.sleep(0.5)
            self.logger.info('Finished adding secret {0}...'.format(key))
        self.logger.info('Finished adding secrets...')


class AgentTestCase(BaseAgentTestCase):

    def setUp(self):
        super(AgentTestCase, self).setUp()
        self._setup_running_manager_attributes()
        self.addCleanup(self._save_manager_logs_after_test)


class AgentTestWithPlugins(AgentTestCase):
    def setUp(self):
        super(AgentTestWithPlugins, self).setUp()

        # Subclasses should set these two values during setup
        self.setup_deployment_id = None
        self.setup_node_id = None

    def get_plugin_data(self, plugin_name, deployment_id):
        """Reading plugin data from agent containers"""

        plugin_path = os.path.join(PLUGIN_STORAGE_DIR,
                                   '{0}.json'.format(plugin_name))
        data = self.read_host_file(plugin_path,
                                   self.setup_deployment_id,
                                   self.setup_node_id)
        if not data:
            return {}
        data = json.loads(data)
        return data.get(deployment_id, {})

    def _get_or_create_wagon(self, plugin_path):
        target_dir = tempfile.mkdtemp(dir=self.workdir)
        return [wagon.create(
            plugin_path,
            archive_destination_dir=target_dir,
            force=True
        )]

    def upload_mock_plugin(self, plugin_name, plugin_path=None):
        self.logger.info(
            'Starting uploading {0} from {1}...'.format(
                plugin_name, plugin_path))
        if not plugin_path:
            plugin_path = test_utils.get_resource(
                'plugins/{0}'.format(plugin_name)
            )

        wagon_paths = self._get_or_create_wagon(plugin_path)
        for wagon_path in wagon_paths:
            yaml_path = os.path.join(plugin_path, 'plugin.yaml')
            with utils.zip_files([wagon_path, yaml_path]) as zip_path:
                self.client.plugins.upload(zip_path)
        time.sleep(500)
        self._wait_for_execution_by_wf_name('install_plugin')
        self.logger.info(
            'Finished uploading {0}...'.format(plugin_name, plugin_path))

    def _wait_for_execution_by_wf_name(self, wf_name):
        executions = self.client.executions.list(
            workflow_id=wf_name,
            include_system_workflows=True,
            sort={'created_at': 'desc'})
        for execution in executions:
            if execution.status not in Execution.END_STATES:
                self.wait_for_execution_to_end(execution)


class PluginsTest(AgentTestWithPlugins, WagonBuilderMixin):
    BLUEPRINT_EXAMPLES = (
        "https://github.com/cloudify-community/"
        "blueprint-examples/archive/master.zip"
    )

    @classmethod
    def setUpClass(cls):
        super(PluginsTest, cls).setUpClass()
        cls.examples_basedir = tempfile.mkdtemp()
        examples_zip = os.path.join(cls.examples_basedir, 'examples.zip')
        with requests.get(cls.BLUEPRINT_EXAMPLES, stream=True) as resp:
            resp.raise_for_status()
            with open(examples_zip, 'wb') as f:
                for part in resp.iter_content(chunk_size=8192):
                    if not part:
                        continue
                    f.write(part)
        zipped_examples = ZipFile(examples_zip)
        zipped_examples.extractall(cls.examples_basedir)
        cls.examples = os.path.join(
            cls.examples_basedir, 'blueprint-examples-master')

    @classmethod
    def tearDownClass(cls):
        super(PluginsTest, cls).tearDownClass()
        shutil.rmtree(cls.examples_basedir, ignore_failure=True)

    @staticmethod
    def get_wagon_path(plugin_path):
        wagons = []
        for filename in os.listdir(plugin_path):
            if filename.endswith('.wgn'):
                wagons.append(os.path.join(plugin_path, filename))
        if wagons:
            return wagons
        raise WagonBuildError(
            'No wagon file was found in the plugin build directory.')

    @property
    def plugin_root_directory(self):
        """ Path to the plugin root directory."""
        raise NotImplementedError('Implemented by plugin test class.')

    def _get_or_create_wagon(self, plugin_path):
        """Overrides the inherited class _create_test_wagon."""
        try:
            return self.get_wagon_path(plugin_path)
        except WagonBuildError:
            self.build_wagon(self.logger)
        return self.get_wagon_path(plugin_path)

    def add_cleanup_deployment(self, deployment_id):
        self.addCleanup(
            self.undeploy_application,
            deployment_id,
            parameters={'ignore_failure': True}
        )

    def check_blueprint(self,
                        blueprint_id,
                        blueprint_path,
                        deployment_inputs,
                        timeout=None):

        self.add_cleanup_deployment(blueprint_id)
        self.deploy_application(
            test_utils.get_resource(blueprint_path),
            timeout_seconds=timeout,
            blueprint_id=blueprint_id,
            deployment_id=blueprint_id,
            inputs=deployment_inputs)
        self.undeploy_application(blueprint_id, timeout)

    def check_hello_world_blueprint(self, iaas, inputs, timeout=400):
        blueprint_path = os.path.join(
            self.examples,
            'hello-world-example', '{iaas}.yaml'.format(iaas=iaas))
        blueprint_id = 'hello-world-{iaas}'.format(iaas=iaas)
        self.check_blueprint(blueprint_id, blueprint_path, inputs, timeout)

    def check_db_lb_app_blueprint(self,
                                  iaas,
                                  timeout,
                                  network_inputs=None,
                                  db_inputs_override=None,
                                  lb_inputs_override=None,
                                  app_inputs_override=None):

        network_inputs = network_inputs or {}
        db_inputs_override = db_inputs_override or {}
        lb_inputs_override = lb_inputs_override or {}
        app_inputs_override = app_inputs_override or {}

        infrastructure_blueprint_path = os.path.join(
            self.examples,
            'db-lb-app/infrastructure/{iaas}.yaml'.format(iaas=iaas))
        infrastructure_blueprint_id = 'infrastructure'

        network_blueprint_id = iaas
        network_blueprint_path = os.path.join(
            self.examples,
            '{iaas}-example-network'.format(iaas=iaas), 'blueprint.yaml')

        db_blueprint_id = 'db'
        db_blueprint_path = os.path.join(
            self.examples,
            'db-lb-app/db/application.yaml')
        db_inputs = {'infrastructure--resource_name_prefix': 'db'}
        db_inputs.update(db_inputs_override)

        lb_blueprint_id = 'lb'
        lb_blueprint_path = os.path.join(
            self.examples,
            'db-lb-app/lb/application.yaml')
        lb_inputs = {'infrastructure--resource_name_prefix': 'lb'}
        lb_inputs.update(lb_inputs_override)

        app_blueprint_id = 'app'
        app_blueprint_path = os.path.join(
            self.examples,
            'db-lb-app/app/application.yaml')
        app_inputs = {'infrastructure--resource_name_prefix': 'app'}
        app_inputs.update(app_inputs_override)

        self.add_cleanup_deployment(network_blueprint_id)
        self.deploy_application(
            test_utils.get_resource(network_blueprint_path),
            timeout_seconds=timeout,
            blueprint_id=network_blueprint_id,
            deployment_id=network_blueprint_id,
            inputs=network_inputs
        )

        self.client.blueprints.upload(
            test_utils.get_resource(infrastructure_blueprint_path),
            infrastructure_blueprint_id)

        self.add_cleanup_deployment(db_blueprint_id)
        self.deploy_application(
            test_utils.get_resource(db_blueprint_path),
            timeout_seconds=timeout,
            blueprint_id=db_blueprint_id,
            deployment_id=db_blueprint_id,
            inputs=db_inputs
        )

        self.add_cleanup_deployment(lb_blueprint_id)
        self.deploy_application(
            test_utils.get_resource(lb_blueprint_path),
            timeout_seconds=timeout,
            blueprint_id=lb_blueprint_id,
            deployment_id=lb_blueprint_id,
            inputs=lb_inputs
        )

        self.add_cleanup_deployment(app_blueprint_id)
        self.deploy_application(
            test_utils.get_resource(app_blueprint_path),
            timeout_seconds=timeout,
            blueprint_id=app_blueprint_id,
            deployment_id=app_blueprint_id,
            inputs=app_inputs
        )

        self.undeploy_application(app_blueprint_id, timeout)
        self.undeploy_application(lb_blueprint_id, timeout)
        self.undeploy_application(db_blueprint_id, timeout)
        self.undeploy_application(network_blueprint_id, timeout)


class PluginTestContainerHosts(PluginsTest):

    def setUp(self):
        super(PluginTestContainerHosts, self).setUp()

    @property
    def plugin_root_directory(self):
        """ Path to the plugin root directory."""
        raise NotImplementedError('Implemented by plugin test class.')

    def prepare_agent_host_container(self,
                                     node_instance_id,
                                     agent_workdir='/root',
                                     agent_tarname='centos-core-agent.tar.gz'):

        self.logger.info(
            'Setting up agent container for {0}'.format(node_instance_id))

        agent_tarpath = os.path.join(agent_workdir, agent_tarname)
        agent_ssl_dir = os.path.join(
            agent_workdir, node_instance_id, 'cloudify/ssl')
        manager_dir = '/opt/manager/resources/packages/agents'
        internal_cert_name = 'cloudify_internal_cert.pem'
        container = self.run_agent_container(
            node_instance_id, self.get_manager_ip(), self.logger)
        self.addCleanup(container.remove)
        self.addCleanup(container.stop)
        temp_agent = tempfile.NamedTemporaryFile()
        temp_cert = tempfile.NamedTemporaryFile()
        self.copy_file_from_manager(
            os.path.join(manager_dir, agent_tarname), temp_agent.name)
        self.copy_file_from_manager(
            '/etc/cloudify/ssl/cloudify_internal_ca_cert.pem',
            temp_cert.name
        )
        self.put_file_on_container(
            open(temp_agent.name, 'rb').read(), agent_workdir, container.id)
        self.extract_tar_on_container(
            agent_tarpath, agent_workdir, container.id)
        container.exec_run('mv {0}/agent-template {1}'.format(
            agent_workdir, os.path.join(agent_workdir, node_instance_id)))
        self.mkdirs_on_container(
            os.path.join(agent_ssl_dir, internal_cert_name),
            container.id)
        self.put_file_on_container(
            self.tar_file_content_for_put_archive(
                open(temp_cert.name, 'r').read(), internal_cert_name),
            agent_ssl_dir,
            container.id
        )
        self.client.node_instances.update(
            node_instance_id,
            runtime_properties={
                'ip':  self.get_container_ip(container),
            })

    def deploy_and_execute_workflow_with_containers(self,
                                                    dsl_path,
                                                    timeout_seconds=240,
                                                    blueprint_id=None,
                                                    deployment_id=None,
                                                    wait_for_execution=True,
                                                    parameters=None,
                                                    inputs=None,
                                                    queue=False,
                                                    node_ids=None,
                                                    **kwargs):

        node_ids = node_ids or []
        node_instances = []

        deployment = BaseTestCase.deploy(dsl_path,
                                         blueprint_id,
                                         deployment_id,
                                         inputs)

        for node_id in node_ids:
            node_instances = self.client.node_instances.list(
                deployment_id=deployment.id, node_id=node_id)
            for node_instance in node_instances:
                self.prepare_agent_host_container(node_instance.id)

        try:
            execution = BaseTestCase.execute_workflow(
                    'install', deployment.id, parameters,
                    timeout_seconds, wait_for_execution, queue=queue, **kwargs)
        except Exception as e:
            self.logger.info('Deployment failed: {0}'.format(e.message))
            executions = [ex for ex in
                          self.client.executions.list(
                              deployment_id=deployment.id)
                          if 'install' in ex.workflow_id]
            if executions:
                self.client.executions.cancel(executions[0].id, force=True)
            self.undeploy_application(deployment.id)
            raise e

        return deployment, execution.id, node_instances

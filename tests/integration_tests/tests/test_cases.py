
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
import logging
import tempfile
import unittest
import subprocess
from contextlib import contextmanager

import wagon
import pytest
from retrying import retry
from requests.exceptions import ConnectionError

import cloudify.utils
from cloudify.snapshots import STATES, SNAPSHOT_RESTORE_FLAG_FILE

from manager_rest.constants import CLOUDIFY_TENANT_HEADER

from integration_tests.framework import utils, docker
from integration_tests.tests import utils as test_utils
from integration_tests.tests.utils import (
    get_resource,
    wait_for_blueprint_upload,
    wait_for_deployment_creation_to_complete,
    wait_for_deployment_deletion_to_complete,
    verify_deployment_env_created,
    run_postgresql_command,
    do_retries,
    do_retries_boolean
)

from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import CloudifyClientError


@pytest.mark.usefixtures("manager_class_fixtures")
@pytest.mark.usefixtures("workdir")
class BaseTestCase(unittest.TestCase):
    """
    A test case for cloudify integration tests.
    """
    def setUp(self):
        self._set_tests_framework_logger()

    def _set_tests_framework_logger(self):
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        self.logger = cloudify.utils.setup_logger(
            self._testMethodName,
            logging.NOTSET,
            handlers=[handler],
        )

    def read_manager_file(self, file_path, no_strip=False):
        """Read a file from the cloudify manager filesystem."""
        return docker.read_file(
            self.env.container_id, file_path, no_strip=no_strip)

    def delete_manager_file(self, file_path, quiet=True):
        """Remove file from a cloudify manager"""
        return docker.execute(
            self.env.container_id, 'rm -rf {0}'.format(file_path))

    def _test_path(self, path, flag='-f'):
        try:
            self.execute_on_manager(['test', flag, path])
            return True
        except subprocess.CalledProcessError:
            return False

    def file_exists(self, path):
        return self._test_path(path, flag='-f')

    def directory_exists(self, path):
        return self._test_path(path, flag='-d')

    def execute_on_manager(self, command):
        """
        Execute a shell command on the cloudify manager container.
        """
        return docker.execute(self.env.container_id, command)

    def copy_file_to_manager(self, source, target, owner=None):
        """Copy a file to the cloudify manager filesystem"""
        ret_val = docker.copy_file_to_manager(
            self.env.container_id,
            source=source, target=target)
        if owner:
            docker.execute(
                self.env.container_id,
                ['chown', owner, target]
            )
        do_retries_boolean(docker.file_exists,
                           container_id=self.env.container_id,
                           file_path=target)
        return ret_val

    def copy_file_from_manager(self, source, target, owner=None):
        """
        Copy a file to the cloudify manager filesystem

        """
        ret_val = docker.copy_file_from_manager(
            self.env.container_id,
            source=source, target=target)
        if owner:
            BaseTestCase.env.chown(owner, target)
        return ret_val

    def restart_service(self, service_name):
        """restart service by name in the manager container"""
        service_command = self.get_service_management_command()
        docker.execute(
            self.env.container_id,
            '{0} stop {1}'.format(service_command, service_name)
        )
        docker.execute(
            self.env.container_id,
            '{0} start {1}'.format(service_command, service_name)
        )

    def get_runtime_property(self, deployment_id, property_name):
        property_list = []
        for inst in self.client.node_instances.list(
                deployment_id=deployment_id):
            inst_properties = inst['runtime_properties'].get(property_name)
            if inst_properties:
                property_list.append(inst_properties)
        return property_list

    @staticmethod
    def do_assertions(assertions_func, timeout=10, **kwargs):
        return test_utils.do_retries(assertions_func,
                                     timeout,
                                     AssertionError,
                                     **kwargs)

    def wait_for_execution_status(self, execution_id, status, timeout=30):
        def assertion():
            self.assertEqual(status,
                             self.client.executions.get(execution_id).status)
        self.do_assertions(assertion, timeout=timeout)

    def execute_workflow(self,
                         workflow_name,
                         deployment_id,
                         parameters=None,
                         timeout_seconds=240,
                         wait_for_execution=True,
                         force=False,
                         queue=False,
                         client=None,
                         **kwargs):
        """A blocking method which runs the requested workflow"""
        client = client or self.client
        execution = client.executions.start(deployment_id, workflow_name,
                                            parameters=parameters or {},
                                            force=force, queue=queue, **kwargs)
        if wait_for_execution:
            self.wait_for_execution_to_end(
                execution,
                client=client,
                timeout_seconds=timeout_seconds)
        return execution

    def deploy(self,
               dsl_path=None,
               blueprint_id=None,
               deployment_id=None,
               inputs=None,
               wait=True,
               client=None,
               runtime_only_evaluation=False,
               blueprint_visibility=None,
               deployment_visibility=None):
        if not (dsl_path or blueprint_id):
            raise RuntimeWarning('Please supply blueprint path '
                                 'or blueprint id for deploying')

        client = client or self.client
        resource_id = uuid.uuid4()
        blueprint_id = blueprint_id or 'blueprint_{0}'.format(resource_id)
        if dsl_path:
            blueprint_upload_kw = {
                'path': dsl_path,
                'entity_id': blueprint_id
            }
            # If not provided, use the client's default
            if blueprint_visibility:
                blueprint_upload_kw['visibility'] = blueprint_visibility
            client.blueprints.upload(**blueprint_upload_kw)
            wait_for_blueprint_upload(blueprint_id, client, True)
            blueprint = client.blueprints.get(blueprint_id)
        else:
            blueprint = None

        deployment_id = deployment_id or 'deployment_{0}'.format(resource_id)
        deployment_create_kw = {
            'blueprint_id': blueprint.id if blueprint else blueprint_id,
            'deployment_id': deployment_id,
            'inputs': inputs,
            'skip_plugins_validation': True,
            'runtime_only_evaluation': runtime_only_evaluation
        }
        # If not provided, use the client's default
        if deployment_visibility:
            deployment_create_kw['visibility'] = deployment_visibility
        deployment = client.deployments.create(**deployment_create_kw)
        if wait:
            wait_for_deployment_creation_to_complete(
                self.env.container_id, deployment_id, client
            )
        return deployment

    def deploy_and_execute_workflow(self,
                                    dsl_path,
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
        deployment = self.deploy(
            dsl_path, blueprint_id, deployment_id, inputs)
        execution = self.execute_workflow(
            workflow_name, deployment.id, parameters,
            timeout_seconds, wait_for_execution, queue=queue, **kwargs)
        return deployment, execution.id

    def deploy_application(self,
                           dsl_path,
                           timeout_seconds=240,
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
        return self.deploy_and_execute_workflow(
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

    def undeploy_application(self,
                             deployment_id,
                             timeout_seconds=240,
                             is_delete_deployment=False,
                             parameters=None,
                             client=None):
        """
        A blocking method which undeploys an application from the provided dsl
        path.
        """
        client = client or self.client
        execution = client.executions.start(deployment_id,
                                            'uninstall',
                                            parameters=parameters)
        self.wait_for_execution_to_end(
            execution, timeout_seconds=timeout_seconds)

        if execution.error and execution.error != 'None':
            raise RuntimeError(
                'Workflow execution failed: {0}'.format(execution.error))
        if is_delete_deployment:
            self.delete_deployment(deployment_id, validate=True, client=client)
        return execution.id

    def get_manager_ip(self):
        return docker.get_manager_ip(self.env.container_id)

    def delete_deployment(self,
                          deployment_id,
                          force=False,
                          validate=False,
                          client=None):
        client = client or self.client
        result = client.deployments.delete(deployment_id,
                                           force=force,
                                           with_logs=True)
        if validate:
            wait_for_deployment_deletion_to_complete(
                deployment_id,
                client
            )
        return result

    def is_node_started(self, node_id):
        node_instance = self.client.node_instances.get(node_id)
        return node_instance['state'] == 'started'

    def wait_for_execution_to_end(self, execution, is_group=False,
                                  timeout_seconds=240, client=None,
                                  require_success=True):
        client = client or self.client
        if is_group:
            get = client.execution_groups.get
        else:
            get = client.executions.get
        deadline = time.time() + timeout_seconds
        while execution.status not in Execution.END_STATES:
            if not is_group:
                assert execution.ended_at is None
            time.sleep(0.5)
            execution = get(execution.id)
            if time.time() > deadline:
                raise utils.TimeoutException(
                    'Execution timed out: \n{0}'
                    .format(json.dumps(execution, indent=2)))
        if require_success and execution.status == Execution.FAILED:
            if is_group:
                # no .error in exec-groups
                raise RuntimeError(
                    'Group execution failed: {0}'.format(execution.status))
            raise RuntimeError(
                'Workflow execution failed: {0} [{1}]'.format(
                    execution.error,
                    execution.status))
        return execution

    def wait_for_snapshot_restore_to_end(self, client=None):
        client = client or self.client

        @retry(stop_max_attempt_number=240, wait_fixed=1000)
        def wait_for_snapshot_status(status):
            assert client.snapshots.get_status()['status'] == status

        # make sure the restore ran and finished
        wait_for_snapshot_status(STATES.RUNNING)
        wait_for_snapshot_status(STATES.NOT_RUNNING)

    def _wait_for_restore_marker_file_to_be_created(self, timeout_seconds=40):
        self.logger.debug("Waiting for snapshot restore marker to be "
                          "created...")
        deadline = time.time() + timeout_seconds
        exists = None
        while not exists:
            time.sleep(0.5)
            exists = self._restore_marker_file_exists()
            if time.time() > deadline:
                self.fail("Timed out waiting for the restore marker file to "
                          "be created.")
        self.logger.debug("Snapshot restore marker file created.")
        return True

    def _restore_marker_file_exists(self):
        return self.file_exists(SNAPSHOT_RESTORE_FLAG_FILE)

    def create_rest_client(self, **kwargs):
        params = {
            'host': self.env.container_ip,
            'cert_path': self.ca_cert,
            **kwargs
        }
        return utils.create_rest_client(**params)

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
                    if base_dir else str(self.workdir))
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

    def wait_for_all_executions_to_end(self, require_success=True):
        executions = self.client.executions.list(include_system_workflows=True)
        for execution in executions:
            if execution['status'] not in Execution.END_STATES:
                self.wait_for_execution_to_end(execution,
                                               require_success=require_success)

    def wait_for_event(self, execution, message, timeout_seconds=240,
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

    def upload_blueprint_resource(self,
                                  dsl_resource_path,
                                  blueprint_id,
                                  client=None):
        client = client or self.client
        blueprint = get_resource(dsl_resource_path)
        client.blueprints.upload(blueprint, entity_id=blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client, True)

    def wait_for_deployment_environment(self, deployment_id):
        do_retries(
            verify_deployment_env_created,
            container_id=self.env.container_id,
            deployment_id=deployment_id,
            client=self.client,
            timeout_seconds=60
        )

    def get_config(self, name=None, scope=None, client=None):
        client = client or self.client
        return client.manager.get_config(name=name, scope=scope)

    def get_service_management_command(self):
        config = self.get_config('service_management')
        service_command = 'systemctl'
        if config.value == 'supervisord':
            service_command = 'supervisorctl -c /etc/supervisord.conf'
        return service_command


class AgentlessTestCase(BaseTestCase):
    def _select(self, query):
        """Run a SELECT query on the manager.

        Note that this will not parse the results, so the calling
        functions must deal with strings as returned by psql
        (eg. false is the string 'f', NULL is the empty string, etc.)
        """
        out = docker.execute(self.env.container_id, [
            'sudo', '-upostgres', 'psql', '-t', '-F,', 'cloudify_db',
            '-c', '\\copy ({0}) to stdout with csv'.format(query)
        ])
        return [line.split(',') for line in out.split('\n') if line.strip()]

    def assert_labels(self, labels_list_1, labels_list_2):
        simplified_labels = set()
        compared_labels_set = set()

        for label in labels_list_1:
            simplified_labels.add((label['key'], label['value']))

        for compared_label in labels_list_2:
            [(key, value)] = compared_label.items()
            compared_labels_set.add((key, value))

        self.assertEqual(simplified_labels, compared_labels_set)

    def manually_update_execution_status(self, new_status, id):
        run_postgresql_command(
            self.env.container_id,
            "UPDATE executions SET status = '{0}' WHERE id = '{1}'"
                .format(new_status, id)
        )


@pytest.mark.usefixtures('dockercompute_plugin')
@pytest.mark.usefixtures('allow_agent')
class AgentTestCase(BaseTestCase):
    pass


class AgentTestWithPlugins(AgentTestCase):
    def setUp(self):
        super(AgentTestWithPlugins, self).setUp()

        # Subclasses should set these two values during setup
        self.setup_deployment_id = None
        self.setup_node_id = None

    def get_plugin_data(self, plugin_name, deployment_id):
        """Reading plugin data from agent containers"""

        plugin_path = f'/tmp/integration-plugin-storage/{plugin_name}.json'
        data = self.read_host_file(plugin_path,
                                   self.setup_deployment_id,
                                   self.setup_node_id)
        if not data:
            return {}
        data = json.loads(data)
        return data.get(deployment_id, {})

    def _get_or_create_wagon(self, plugin_path):
        target_dir = tempfile.mkdtemp(dir=str(self.workdir))
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
        self.logger.info(
            'Finished uploading {0}...'.format(plugin_name))

    def _wait_for_execution_by_wf_name(self, wf_name):
        executions = self.client.executions.list(
            workflow_id=wf_name,
            include_system_workflows=True,
            sort={'created_at': 'desc'})
        for execution in executions:
            if execution.status not in Execution.END_STATES:
                self.wait_for_execution_to_end(execution)

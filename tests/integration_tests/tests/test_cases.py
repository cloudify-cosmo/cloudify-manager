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

import json
import datetime
import yaml
import tarfile
import logging
import os
import sys
import shutil
import time
import uuid
import tempfile
import unittest
import sh
from contextlib import contextmanager

import nose.tools

import cloudify.utils
import cloudify.logs
import cloudify.event

from logging.handlers import RotatingFileHandler

from manager_rest.utils import mkdirs
from manager_rest.constants import CLOUDIFY_TENANT_HEADER

from integration_tests.framework import utils, hello_world, docl
from integration_tests.framework.flask_utils import reset_storage
from integration_tests.framework.riemann import RIEMANN_CONFIGS_DIR
from integration_tests.tests import utils as test_utils
from integration_tests.framework.constants import (PLUGIN_STORAGE_DIR,
                                                   CLOUDIFY_USER)


class BaseTestCase(unittest.TestCase):
    """
    A test case for cloudify integration tests.
    """

    env = None

    @classmethod
    def setUpClass(cls):
        import integration_tests.framework.env
        BaseTestCase.env = integration_tests.framework.env.instance

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
        self.logger.debug('_save_manager_logs_after_test started')
        logs_dir = os.environ.get('CFY_LOGS_PATH')
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
            'Saving manager logs for test:  {0}'.format(test_path[-1]))
        logs_dir = os.path.join(os.path.expanduser(logs_dir), *test_path)
        mkdirs(logs_dir)
        target = os.path.join(logs_dir, 'logs.tar.gz')
        self.cfy.logs.download(output_path=target)
        if purge:
            self.cfy.logs.purge(force=True)

        self.logger.debug('opening tar.gz: {0}'.format(target))
        with tarfile.open(target) as tar:
            tar.extractall(path=logs_dir)
        self.logger.debug('removing {0}'.format(target))
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
    def copy_file_to_manager(source, target, owner=None):
        """
        Copy a file to the cloudify manager filesystem

        """
        ret_val = docl.copy_file_to_manager(source=source, target=target)
        if owner:
            BaseTestCase.env.chown(owner, target)
        return ret_val

    @staticmethod
    def write_data_to_file_on_manager(data,
                                      target_path,
                                      to_json=False,
                                      owner=None):
        with tempfile.NamedTemporaryFile() as f:
            if to_json:
                data = json.dumps(data)
            f.write(data)
            f.flush()
            BaseTestCase.copy_file_to_manager(f.name, target_path, owner=owner)

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
    def publish_riemann_event(deployment_id,
                              node_name,
                              node_id='',
                              host='localhost',
                              service='service',
                              state='',
                              metric=0,
                              ttl=60):
        event = {
            'host': host,
            'service': service,
            'state': state,
            'metric': metric,
            'time': int(time.time()),
            'node_name': node_name,
            'node_id': node_id,
            'ttl': ttl
        }
        queue = '{0}-riemann'.format(deployment_id)
        routing_key = deployment_id
        test_utils.publish_event(queue, routing_key, event)

    @staticmethod
    def execute_workflow(workflow_name, deployment_id,
                         parameters=None,
                         timeout_seconds=240,
                         wait_for_execution=True):
        """
        A blocking method which runs the requested workflow
        """
        client = test_utils.create_rest_client()

        execution = client.executions.start(deployment_id, workflow_name,
                                            parameters=parameters or {})

        if wait_for_execution:
            BaseTestCase.wait_for_execution_to_end(
                    execution,
                    timeout_seconds=timeout_seconds)

        return execution

    @staticmethod
    def deploy(dsl_path, blueprint_id=None, deployment_id=None, inputs=None):
        client = test_utils.create_rest_client()
        if not blueprint_id:
            blueprint_id = str(uuid.uuid4())
        blueprint = client.blueprints.upload(dsl_path, blueprint_id)
        if deployment_id is None:
            deployment_id = str(uuid.uuid4())
        deployment = client.deployments.create(
                blueprint.id,
                deployment_id,
                inputs=inputs)

        test_utils.wait_for_deployment_creation_to_complete(
            deployment_id=deployment_id)
        return deployment

    @staticmethod
    def deploy_and_execute_workflow(dsl_path,
                                    workflow_name,
                                    timeout_seconds=240,
                                    blueprint_id=None,
                                    deployment_id=None,
                                    wait_for_execution=True,
                                    parameters=None,
                                    inputs=None):
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
                timeout_seconds, wait_for_execution)
        return deployment, execution.id

    @staticmethod
    def deploy_application(dsl_path,
                           timeout_seconds=60,
                           blueprint_id=None,
                           deployment_id=None,
                           wait_for_execution=True,
                           inputs=None):
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
                inputs=inputs)

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
            BaseTestCase.delete_deployment(deployment_id)

    @staticmethod
    def get_manager_ip():
        return utils.get_manager_ip()

    @staticmethod
    def delete_deployment(deployment_id, ignore_live_nodes=False):
        client = test_utils.create_rest_client()
        return client.deployments.delete(deployment_id,
                                         ignore_live_nodes=ignore_live_nodes)

    @staticmethod
    def is_node_started(node_id):
        client = test_utils.create_rest_client()
        node_instance = client.node_instances.get(node_id)
        return node_instance['state'] == 'started'

    @staticmethod
    def wait_for_execution_to_end(execution,
                                  timeout_seconds=240,
                                  tolerate_client_errors=False):
        return test_utils.wait_for_execution_to_end(
            execution,
            timeout_seconds,
            tolerate_client_errors,
        )

    @staticmethod
    def is_riemann_core_up(deployment_id):
        core_indicator = os.path.join(RIEMANN_CONFIGS_DIR, deployment_id, 'ok')
        try:
            out = docl.read_file(core_indicator)
            return out == 'ok'
        except sh.ErrorReturnCode:
            return False

    @contextmanager
    def client_using_tenant(self, client, tenant_name):
        curr_tenant = client._client.headers.get(CLOUDIFY_TENANT_HEADER)
        try:
            client._client.headers[CLOUDIFY_TENANT_HEADER] = tenant_name
            yield
        finally:
            client._client.headers[CLOUDIFY_TENANT_HEADER] = curr_tenant


class AgentlessTestCase(BaseTestCase):
    run_storage_reset = True

    def setUp(self):
        super(AgentlessTestCase, self).setUp()
        self._setup_running_manager_attributes()
        if self.run_storage_reset:
            reset_storage()

        self.addCleanup(self._save_manager_logs_after_test)


class BaseAgentTestCase(BaseTestCase):

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

    @nose.tools.nottest
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


class ManagerTestCase(BaseAgentTestCase):

    def setUp(self):
        super(ManagerTestCase, self).setUp()
        self.manager_label = 'own_manager={0}'.format(self._testMethodName)

    def prepare_bootstrappable_container(self,
                                         additional_exposed_ports=None):
        self.addCleanup(
            lambda: self.env.clean_manager(
                label=[self.manager_label],
                clean_tag=True))
        self.addCleanup(self._save_manager_logs_after_test, purge=False)
        self.env.prepare_bootstrappable_container(
            label=[self.manager_label],
            additional_exposed_ports=additional_exposed_ports)

    def bootstrap_prepared_container(self,
                                     inputs=None,
                                     modify_blueprint_func=None):
        self.env.bootstrap_prepared_container(
            inputs=inputs,
            modify_blueprint_func=modify_blueprint_func)
        self._setup_running_manager_attributes()

    def bootstrap(self,
                  inputs=None,
                  modify_blueprint_func=None,
                  additional_exposed_ports=None):
        """
        The modify_blueprint_func can be used in cases where there is need to
        perform some modification to the manager blueprint. The signature of
        this function is (patcher, manager_blueprint_dir) where patcher is a
        yaml patcher that can be used to override the main blueprint file.
        manager blueprint dir can be used in case the tests needs to modify
        other files in the the manager blueprint directory.

        :param inputs:
        :param modify_blueprint_func: Modification func
        :param additional_exposed_ports: additional ports that should be
               exposed on the newly bootstrapped container
        :return:
        """
        inputs = self._update_inputs_with_dev_resource_urls(inputs)
        self.prepare_bootstrappable_container(
            additional_exposed_ports=additional_exposed_ports)
        self.bootstrap_prepared_container(
            inputs=inputs,
            modify_blueprint_func=modify_blueprint_func)

    @staticmethod
    def _update_inputs_with_dev_resource_urls(inputs):
        """Update the inputs to be sent to the manager with the resource URLs
        from dev_resource_urls.yaml

        To be used during development, when the integration test needs updated
        code during bootstrap (as opposed to the mount docl does after
        bootstrap)

        :param inputs: inputs dict
        :return: The updated inputs dict
        """
        inputs = inputs or {}
        dev_resources_path = test_utils.get_resource('dev_resource_urls.yaml')
        with open(dev_resources_path, 'r') as f:
            inputs.update(yaml.load(f))
        return inputs

    def run_manager(self):
        self.addCleanup(
            lambda: self.env.clean_manager(label=[self.manager_label]))
        self.addCleanup(self._save_manager_logs_after_test, purge=False)
        self.env.run_manager(label=[self.manager_label])
        self._setup_running_manager_attributes()

    def restart_manager(self):
        self.logger.info('Restarting manager')
        docl.restart_manager()
        self.env.start_events_printer()

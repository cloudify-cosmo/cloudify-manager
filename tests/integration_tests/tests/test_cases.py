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
import yaml
import logging
import os
import shutil
import time
import tempfile
import unittest

import nose.tools

import cloudify.utils
import cloudify.logs
import cloudify.event

from manager_rest.utils import mkdirs

from integration_tests import utils
from integration_tests import hello_world
from integration_tests import docl
from integration_tests import postgresql
from integration_tests.utils import get_resource as resource


class BaseTestCase(unittest.TestCase):
    """
    A test case for cloudify integration tests.
    """

    def setUp(self):
        import integration_tests.env
        self.env = integration_tests.env.instance
        self.workdir = tempfile.mkdtemp(
            dir=self.env.test_working_dir,
            prefix='{0}-'.format(self._testMethodName))
        self.cfy = utils.get_cfy()
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)
        self.logger = cloudify.utils.setup_logger(self._testMethodName,
                                                  logging.INFO)
        self.client = None

    def _setup_running_manager_attributes(self):
        self.client = utils.create_rest_client()

    def tearDown(self):
        self.env.stop_dispatch_processes()

    def _save_logs(self, purge=True):
        logs_dir = os.environ.get('CFY_LOGS_PATH')
        if not logs_dir:
            return
        logs_dir = os.path.join(logs_dir, *self.id().split('.'))
        mkdirs(logs_dir)
        self.cfy.logs.download(output_path=logs_dir)
        if purge:
            self.cfy.logs.purge(force=True)

    @staticmethod
    def read_manager_file(file_path, no_strip=False):
        """
        Read a file from the cloudify manager filesystem.
        """
        return docl.read_file(file_path, no_strip=no_strip)

    @staticmethod
    def execute_on_manager(command, quiet=True):
        """
        Execute a shell command on the cloudify manager container.
        """
        return docl.execute(command, quiet)

    @staticmethod
    def copy_file_to_manager(source, target):
        """
        Copy a file to the cloudify manager filesystem

        """
        return docl.copy_file_to_manager(source=source, target=target)

    def get_plugin_data(self, plugin_name, deployment_id):
        """
        Retrieve the plugin state for a certain deployment.

        :param deployment_id: the deployment id in question.
        :param plugin_name: the plugin in question.
        :return: plugin data relevant for the deployment.
        :rtype dict
        """
        storage_file_path = os.path.join(
            self.env.plugins_storage_dir,
            '{0}.json'.format(plugin_name)
        )
        if not os.path.exists(storage_file_path):
            return {}
        with open(storage_file_path, 'r') as f:
            data = json.load(f)
            if deployment_id not in data:
                data[deployment_id] = {}
            return data.get(deployment_id)

    def clear_plugin_data(self, plugin_name):
        """
        Clears plugin state.

        :param plugin_name: the plugin in question.
        """
        storage_file_path = os.path.join(
            self.env.plugins_storage_dir,
            '{0}.json'.format(plugin_name)
        )
        if os.path.exists(storage_file_path):
            os.remove(storage_file_path)

    @staticmethod
    def do_assertions(assertions_func, timeout=10, **kwargs):
        return utils.do_retries(assertions_func,
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
        utils.publish_event(queue, routing_key, event)


class AgentlessTestCase(BaseTestCase):

    def setUp(self):
        super(AgentlessTestCase, self).setUp()
        self._setup_running_manager_attributes()
        utils.restore_provider_context()
        self.addCleanup(self._save_logs)

    def tearDown(self):
        postgresql.reset_data()
        super(AgentlessTestCase, self).tearDown()


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
        self.addCleanup(self._save_logs)


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
        self.addCleanup(self._save_logs, purge=False)
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
        dev_resources_path = resource('dev_resource_urls.yaml')
        with open(dev_resources_path, 'r') as f:
            inputs.update(yaml.load(f))
        return inputs

    def run_manager(self):
        self.addCleanup(
            lambda: self.env.clean_manager(label=[self.manager_label]))
        self.addCleanup(self._save_logs, purge=False)
        self.env.run_manager(label=[self.manager_label])
        self._setup_running_manager_attributes()

    def restart_manager(self):
        self.logger.info('Restarting manager')
        docl.restart_manager()
        self.env.start_events_printer()

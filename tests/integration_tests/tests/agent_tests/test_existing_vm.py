########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import uuid
from os.path import join

from integration_tests.framework import utils
from integration_tests import AgentTestWithPlugins
from integration_tests.tests.utils import get_resource as resource


class BaseExistingVMTest(AgentTestWithPlugins):
    def setUp(self):
        super(BaseExistingVMTest, self).setUp()
        self.setup_deployment_id = 'd{0}'.format(uuid.uuid4())
        self.setup_node_id = 'setup_host'
        dsl_path = resource("dsl/agent_tests/existing-vm-setup.yaml")
        self.deploy_application(dsl_path,
                                deployment_id=self.setup_deployment_id)

    def _get_ssh_key_content(self):
        ssh_key_path = self.get_host_key_path(
            node_id=self.setup_node_id,
            deployment_id=self.setup_deployment_id
        )
        return self.read_manager_file(ssh_key_path)

    def _get_host_ip(self):
        return self.get_host_ip(
            node_id=self.setup_node_id,
            deployment_id=self.setup_deployment_id
        )


class ExistingVMTest(BaseExistingVMTest):
    def test_existing_vm(self):
        dsl_path = resource("dsl/agent_tests/existing-vm.yaml")
        inputs = {
            'ip': self._get_host_ip(),
            'agent_key': self.get_host_key_path(
                node_id=self.setup_node_id,
                deployment_id=self.setup_deployment_id),
        }
        deployment, _ = self.deploy_application(dsl_path, inputs=inputs)
        plugin_data = self.get_plugin_data('testmockoperations', deployment.id)
        self.assertEqual(1, len(plugin_data['mock_operation_invocation']))


class SecretAgentKeyTest(BaseExistingVMTest):
    def test_secret_ssh_key_in_existing_vm(self):
        ssh_key_content = self._get_ssh_key_content()
        self.client.secrets.create('agent_key', ssh_key_content)
        dsl_path = resource(
            'dsl/agent_tests/secret-ssh-key-in-existing-vm.yaml'
        )
        inputs = {'ip': self._get_host_ip()}
        deployment, _ = self.deploy_application(dsl_path, inputs=inputs)
        plugin_data = self.get_plugin_data('testmockoperations', deployment.id)
        self.assertEqual(1, len(plugin_data['mock_operation_invocation']))


class HostPluginTest(BaseExistingVMTest):
    BLUEPRINTS = 'dsl/agent_tests/plugin-requires-old-package-blueprint'

    def test_source_plugin_requires_old_package(self):
        self._test_host_plugin_requires_old_package(
            join(self.BLUEPRINTS, 'source_plugin_blueprint.yaml')
        )

    def test_wagon_plugin_requires_old_package(self):
        wagon_path = self._get_plugin_wagon(
            'requires_old_package_plugin-1.0-py27-none-any.wgn'
        )
        plugin_yaml = join(self.BLUEPRINTS,
                           'plugins',
                           'old_package_wagon_plugin.yaml')
        yaml_path = resource(plugin_yaml)
        with utils.zip_files([wagon_path, yaml_path]) as zip_path:
            self.client.plugins.upload(zip_path)
            self._wait_for_execution_by_wf_name('install_plugin')
        self._test_host_plugin_requires_old_package(
            join(self.BLUEPRINTS, 'wagon_plugin_blueprint.yaml')
        )

    def _test_host_plugin_requires_old_package(self, blueprint_path):
        dsl_path = resource(blueprint_path)
        inputs = {
            'server_ip': self._get_host_ip(),
            'agent_private_key_path': self.get_host_key_path(
                node_id=self.setup_node_id,
                deployment_id=self.setup_deployment_id),
            'agent_user': 'root'
        }
        deployment, _ = self.deploy_application(dsl_path, inputs=inputs)
        self.undeploy_application(deployment.id)

    def _get_plugin_wagon(self, name):
        aws_url = 'http://cloudify-tests-files.s3-eu-west-1.amazonaws.com/'
        wagon_url = join(aws_url, 'plugins', name)
        self.logger.info('Retrieving wagon: {0}'.format(wagon_url))
        tmp_file = join(self.workdir, name)
        return utils.download_file(wagon_url, tmp_file)

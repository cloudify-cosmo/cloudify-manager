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

import os

from integration_tests.tests import utils as test_utils
from .test_base import TestSSLRestBase

agent_prop_path = (
    'node_templates.vm.properties.agent_config.extra.agent_rest_cert_path')
broker_prop_path = (
    'node_templates.vm.properties.agent_config.extra.broker_ssl_cert_path')


class CertsLocationTestBase(TestSSLRestBase):

    rest_path = None
    broker_path = None

    def _run_test(self, override_app_agent_config=False):
        self.bootstrap_secured_manager()
        if override_app_agent_config:
            update_func = self._update_blueprint
        else:
            update_func = None
        deployment = self.test_hello_world(
            modify_blueprint_func=update_func,
            skip_uninstall=True)
        self._assert_file_exists(
            self.rest_path,
            assert_exists_on_manager=not override_app_agent_config,
            deployment_id=deployment.id)
        self._assert_file_exists(
            self.broker_path,
            assert_exists_on_manager=not override_app_agent_config,
            deployment_id=deployment.id)

    def _assert_file_exists(self,
                            path,
                            assert_exists_on_manager,
                            deployment_id):
        path = path.replace('~', '/root')
        if assert_exists_on_manager:
            self.read_manager_file(path)
        self.read_host_file(path, node_id='vm', deployment_id=deployment_id)

    def _update_blueprint(self, patcher, _):
        blueprint_override = {agent_prop_path: self.rest_path,
                              broker_prop_path: self.broker_path}
        for key, value in blueprint_override.items():
            patcher.set_value(key, value)

    def get_manager_blueprint_inputs(self):
        inputs = super(CertsLocationTestBase,
                       self).get_manager_blueprint_inputs()
        cert_path = os.path.join(self.workdir, 'broker.crt')
        key_path = os.path.join(self.workdir, 'broker.key')
        test_utils.create_self_signed_certificate(
                target_certificate_path=cert_path,
                target_key_path=key_path,
                common_name='cloudify-manager')
        with open(cert_path) as f:
            cert_content = f.read()
        with open(key_path) as f:
            key_content = f.read()
        inputs.update({'rabbitmq_ssl_enabled': True,
                       'rabbitmq_cert_public': cert_content,
                       'rabbitmq_cert_private': key_content})
        return inputs


class CloudifyAgentCertsLocationTest(CertsLocationTestBase):

    def test_certs_location_default(self):
        self.rest_path = '~/.cloudify/certs/rest.crt'
        self.broker_path = '~/.cloudify/certs/broker.crt'
        self._run_test()

    def test_certs_location_absolute(self):
        self.rest_path = '/root/MyRest.cert'
        self.broker_path = '/root/asd/MyBroker.cert'
        self._run_test(override_app_agent_config=True)

    def test_certs_location_relative(self):
        self.rest_path = '~/MyRest2.cert'
        self.broker_path = '~/some_dir/asd/MyBroker2.cert'
        self._run_test(override_app_agent_config=True)


class ManagerInputsCertsLocationTest(CertsLocationTestBase):

    def test_certs_location_from_manager_inputs(self):
        self.rest_path = '~/asd/MyRest3.cert'
        self.broker_path = '/root/MyBroker3.cert'
        self._run_test()

    def get_manager_blueprint_inputs(self):
        inputs = super(ManagerInputsCertsLocationTest,
                       self).get_manager_blueprint_inputs()
        inputs.update({'agent_rest_cert_path': self.rest_path,
                       'broker_ssl_cert_path': self.broker_path})
        return inputs

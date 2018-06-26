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
import uuid
import shutil

from integration_tests import AgentTestWithPlugins, BaseTestCase
from integration_tests.tests.utils import get_resource as resource


class TestPluginUpdate(AgentTestWithPlugins):
    def test_plugin_update(self):
        self.setup_deployment_id = 'd{0}'.format(uuid.uuid4())
        self.setup_node_id = 'node'
        self.plugin_name = 'version-aware-plugin'
        self.base_name = 'base'
        self.mod_name = 'mod'

        # Upload V1.0 and V2.0 plugins
        self.upload_mock_plugin(self.plugin_name)
        self._upload_v_2_0_plugin()

        self._upload_blueprints_and_deploy_base()

        # Execute base (V 1.0) workflows
        self._execute_workflows()
        self._assert_on_values('1.0')

        self._perform_update()

        # Execute mod (V 2.0) workflows
        self._execute_workflows()
        self._assert_on_values('2.0')

    def _perform_update(self):
        self.client.deployment_updates.update_with_existing_blueprint(
            deployment_id=self.setup_deployment_id,
            blueprint_id=self.mod_name
        )
        self._wait_for_execution_by_wf_name('update')

    def _upload_v_2_0_plugin(self):
        source_dir = resource('plugins/{0}'.format(self.plugin_name))
        target_dir = os.path.join(self.workdir, self.plugin_name)
        shutil.copytree(source_dir, target_dir)

        self._replace_version(target_dir)
        self.upload_mock_plugin(self.plugin_name, plugin_path=target_dir)

    @staticmethod
    def _replace_version(target_dir):
        """ https://stackoverflow.com/a/4205918/978089 """

        for dname, dirs, files in os.walk(target_dir):
            for fname in files:
                fpath = os.path.join(dname, fname)
                with open(fpath) as f:
                    s = f.read()
                s = s.replace('1.0', '2.0')
                with open(fpath, 'w') as f:
                    f.write(s)

    def _assert_on_values(self, version):
        # Calling like this because "cda" op/wf would be written on the manager
        # as opposed to the host
        cda_data = BaseTestCase.get_plugin_data(
            self,
            plugin_name='cda',
            deployment_id=self.setup_deployment_id
        )
        self.assertEqual(cda_data['cda_wf'], version)
        self.assertEqual(cda_data['cda_op'], version)

        host_data = self.get_plugin_data('host', self.setup_deployment_id)
        self.assertEqual(host_data['host_op'], version)

    def _upload_blueprints_and_deploy_base(self):
        self.deploy_application(
            dsl_path=self._get_dsl_path(self.base_name),
            blueprint_id=self.base_name,
            deployment_id=self.setup_deployment_id
        )

        self.client.blueprints.upload(
            path=self._get_dsl_path(self.mod_name),
            entity_id=self.mod_name
        )

    @staticmethod
    def _get_dsl_path(name):
        return resource('dsl/agent_tests/plugin_update_{0}.yaml'.format(name))

    def _execute_workflows(self):
        for wf in ('test_cda_wf', 'test_cda_op', 'test_host_op'):
            self.execute_workflow(wf, self.setup_deployment_id)

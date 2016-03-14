########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

from testenv import ProcessModeTestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.processes.celery import CeleryWorkerProcess


class PluginWorkdirTest(ProcessModeTestCase):

    def test_plugin_workdir(self):
        filename = 'test_plugin_workdir.txt'
        host_content = 'HOST_CONTENT'
        central_content = 'CENTRAL_CONTENT'

        dsl_path = resource("dsl/plugin_workdir.yaml")
        deployment, _ = deploy(dsl_path,
                               inputs={
                                   'filename': filename,
                                   'host_content': host_content,
                                   'central_content': central_content
                               })
        host_id = self.client.node_instances.list(node_id='host').items[0].id

        from testenv import testenv_instance
        test_workdir = testenv_instance.test_working_dir
        central_agent = CeleryWorkerProcess(['cloudify.management'],
                                            test_workdir)
        host_agent = CeleryWorkerProcess([host_id], test_workdir)

        central_file = os.path.join(
            central_agent.workdir, 'deployments', deployment.id, 'plugins',
            'testmockoperations', filename)
        host_file = os.path.join(
            host_agent.workdir, 'plugins', 'testmockoperations', filename)

        with open(central_file) as f:
            self.assertEqual(central_content, f.read())
        with open(host_file) as f:
            self.assertEqual(host_content, f.read())

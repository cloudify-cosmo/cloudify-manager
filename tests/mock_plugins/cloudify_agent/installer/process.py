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
import shutil

from cloudify import ctx
from cloudify import context
from testenv.processes.celery import CeleryWorkerProcess
from mock_plugins.cloudify_agent.installer import AgentInstaller


class ProcessBackedAgentInstaller(AgentInstaller):

    def create(self):
        process = CeleryWorkerProcess(
            queues=[self.agent_queue],
            name=self.agent_name,
            test_working_dir=os.environ['TEST_WORKING_DIR']
        )
        process.create_dirs()
        self._install_plugin('cloudify_agent', process.envdir)

    def configure(self):
        pass

    def start(self):
        process = CeleryWorkerProcess(
            queues=[self.agent_queue],
            name=self.agent_name,
            test_working_dir=os.environ['TEST_WORKING_DIR'],
            additional_includes=self._build_additional_includes()
        )
        process.start()

    def stop(self):
        process = CeleryWorkerProcess(
            queues=[self.agent_queue],
            name=self.agent_name,
            test_working_dir=os.environ['TEST_WORKING_DIR']
        )
        process.stop()

    def restart(self):
        self.stop()
        self.start()

    def delete(self):
        pass

    def _build_additional_includes(self):
        includes = ['script_runner.tasks']
        if ctx.type == context.DEPLOYMENT:
            if 'workflows' in self.agent_name:
                # the workflows worker needs
                # the default workflows
                # available
                includes.append('cloudify.plugins.workflows')
            else:
                # the operation worker needs
                # the riemann controller for
                # loading riemann cores and
                # the diamond plugin for policies
                includes.append('riemann_controller.tasks')
                includes.append('diamond_agent.tasks')
        return includes

    @staticmethod
    def _install_plugin(plugin,
                        env_dir):
        source_plugin_path = os.path.join(
            os.environ['MOCK_PLUGINS_PATH'], plugin)

        target_plugin_path = os.path.join(env_dir, plugin)

        if not os.path.exists(target_plugin_path):
            shutil.copytree(
                src=source_plugin_path,
                dst=target_plugin_path,
                ignore=shutil.ignore_patterns('*.pyc')
            )

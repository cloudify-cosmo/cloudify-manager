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
from mock import MagicMock

from cloudify import ctx
from cloudify.exceptions import NonRecoverableError
from cloudify.celery import celery
from cloudify import context
from cloudify.utils import setup_logger


from cloudify_agent.installer import AgentInstaller
from cloudify_agent.api.plugins.installer import PluginInstaller

from testenv.processes.celery import CeleryWorkerProcess


logger = setup_logger('testenv.mocks')


class ConsumerBackedAgentInstaller(AgentInstaller):

    def create_agent(self):
        ctx.logger.info('Created Agent {0}'
                        .format(self.cloudify_agent['name']))

    def configure_agent(self):
        ctx.logger.info('Configured Agent {0}'
                        .format(self.cloudify_agent['name']))

    def start_agent(self):

        name = self.cloudify_agent['name']
        queue = self.cloudify_agent['queue']

        ctx.logger.info('Starting Agent {0}'.format(name))
        ctx.logger.info('Adding a consumer with queue: {0}'
                        .format(queue))
        celery.control.add_consumer(
            queue=queue,
            destination=['celery@cloudify.management']
        )
        ctx.logger.info('Started Agent {0}'.format(name))

    def stop_agent(self):
        name = self.cloudify_agent['name']
        queue = self.cloudify_agent['queue']

        ctx.logger.info('Stopping Agent {0}'.format(name))
        ctx.logger.info('Canceling a consumer with queue: {0}'
                        .format(queue))
        celery.control.cancel_consumer(
            queue=queue,
            destination=['celery@cloudify.management']
        )
        ctx.logger.info('Stopped Agent {0}'.format(name))

    def restart_agent(self):
        ctx.logger.info('Restarted Agent {0}'
                        .format(self.cloudify_agent['name']))

    def delete_agent(self):
        ctx.logger.info('Deleted Agent {0}'
                        .format(self.cloudify_agent['name']))

    @property
    def runner(self):
        return MagicMock()


class ProcessBackedAgentInstaller(AgentInstaller):

    def create_agent(self):
        ctx.logger.info('Creating Agent {0}'
                        .format(self.cloudify_agent['name']))

        process = CeleryWorkerProcess(
            queues=[self.cloudify_agent['queue']],
            test_working_dir=os.environ['TEST_WORKING_DIR']
        )
        process.create_dirs()
        ctx.logger.info('Created Agent {0}'.format(self.cloudify_agent[
            'name']))

    def configure_agent(self):
        ctx.logger.info('Configured Agent {0}'
                        .format(self.cloudify_agent['name']))

    def start_agent(self):

        name = self.cloudify_agent['name']
        queue = self.cloudify_agent['queue']

        ctx.logger.info('Starting Agent {0}'.format(name))
        process = CeleryWorkerProcess(
            queues=[queue],
            test_working_dir=os.environ['TEST_WORKING_DIR'],
            additional_includes=self._build_additional_includes()
        )
        process.start()
        ctx.logger.info('Started Agent {0}'.format(name))

    def stop_agent(self):
        name = self.cloudify_agent['name']
        queue = self.cloudify_agent['queue']

        ctx.logger.info('Stopping Agent {0}'.format(name))
        process = CeleryWorkerProcess(
            queues=[queue],
            test_working_dir=os.environ['TEST_WORKING_DIR']
        )
        process.start()
        ctx.logger.info('Stopped Agent {0}'.format(name))

    def restart_agent(self):
        self.stop_agent()
        self.start_agent()

    def delete_agent(self):
        ctx.logger.info('Deleted Agent {0}'
                        .format(self.cloudify_agent['name']))

    def _build_additional_includes(self):
        includes = ['script_runner.tasks']
        if ctx.type == context.DEPLOYMENT:
            if 'workflows' in self.cloudify_agent['name']:
                # the workflows Agent needs
                # the default workflows
                # available
                includes.append('cloudify.plugins.workflows')
            else:
                # the operation Agent needs
                # the riemann controller for
                # loading riemann cores and
                # the diamond plugin for policies
                includes.append('riemann_controller.tasks')
                includes.append('diamond_agent.tasks')
        return includes


class ConsumerBackedPluginInstaller(PluginInstaller):

    def install(self, source, args=''):
        pass


class ProcessBackedPluginInstaller(PluginInstaller):

    def install(self, source, args=''):

        source_plugin_path = os.path.join(
            os.environ['MOCK_PLUGINS_PATH'],
            source
        )

        target_plugin_path = os.path.join(
            os.environ['ENV_DIR'],
            source
        )

        if not os.path.exists(target_plugin_path):

            # just copy the plugin
            # directory to the
            # Agent environment

            ctx.logger.info('Copying {0} --> {1}'
                            .format(source_plugin_path,
                                    target_plugin_path))

            shutil.copytree(
                src=source_plugin_path,
                dst=target_plugin_path,
                ignore=shutil.ignore_patterns('*.pyc')
            )


def task_exists(name, *args):
    logger.info('task_exists invoked with : {0}'
                .format(args))
    if 'non_existent' in name:
        logger.info('non_existent operation, raising NonRecoverableError')
        raise NonRecoverableError('non_existent operation [{0}]'.format(name))
    return True


def agent_exists(*_):
    return True


from cloudify.workflows import tasks

from cloudify_agent.installer import operations as installer
from cloudify_agent import operations
from cloudify_agent.api import utils as api_utils


############################################################################
# Apply various mocks. this code is executed when the celery master first
# launches, by including this file in the celery includes list
############################################################################

# This is needed because in this
# environment, all tasks are sent to
# the management worker, and handled by
# different consumers. The original method
# asserts that tasks are being sent to
# different workers,
tasks.verify_task_registered = task_exists

# this is needed in order for the plugin installation process
# to complete successfully, which tries to load daemons using the
# DaemonFactory and other utility methods.. see
# 'cloudify_agent.operations.install_plugins'
operations.DaemonFactory = MagicMock()
operations.get_daemon_name = MagicMock()
operations.get_daemon_user = MagicMock()
operations.get_daemon_storage_dir = MagicMock()


# this is needed in order to mock the agent installation process,
# which cannot be the full blown regular install. However, we do want to run
# and test the configuration and decorator code itself.
if os.environ.get('PROCESS_MODE'):
    installer.LocalLinuxAgentInstaller = ProcessBackedAgentInstaller
    installer.RemoteLinuxAgentInstaller = ProcessBackedAgentInstaller
    operations.PluginInstaller = ProcessBackedPluginInstaller
else:
    # this is needed because the agent installer does a verification
    # that the agent exists, by name, and in this environment, we are using
    # consumers, not actual processes with different names.
    # see 'cloudify_agent.installer.operations.start'
    api_utils.get_agent_stats = agent_exists

    installer.LocalLinuxAgentInstaller = ConsumerBackedAgentInstaller
    installer.RemoteLinuxAgentInstaller = ConsumerBackedAgentInstaller
    operations.PluginInstaller = ConsumerBackedPluginInstaller

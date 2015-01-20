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

from cloudify import ctx
from cloudify.celery import celery

from mock_plugins.worker_installer import WorkerInstaller


class ConsumerBackedWorkerInstaller(WorkerInstaller):

    def install(self):
        ctx.logger.info('Installing worker {0}'
                        .format(self.agent_name))
        ctx.logger.info('Installed worker {0}'
                        .format(self.agent_name))

    def start(self):
        worker_name = self.agent_name
        ctx.logger.info('Starting worker {0}'.format(worker_name))
        celery.control.add_consumer(
            queue=worker_name,
            destination=['celery@celery.cloudify.management']
        )
        ctx.logger.info('Started worker {0}'.format(worker_name))

    def stop(self):
        ctx.logger.info('Stopping worker {0}'
                        .format(self.agent_name))
        celery.control.cancel_consumer(
            queue=self.agent_name,
            destination=['celery.cloudify.management']
        )
        ctx.logger.info('Stopped worker {0}'
                        .format(self.agent_name))

    def restart(self):
        ctx.logger.info('Re-started worker {0}'
                        .format(self.agent_name))

    def uninstall(self):
        ctx.logger.info('Uninstalling worker {0}'
                        .format(self.agent_name))
        ctx.logger.info('Uninstalled worker {0}'
                        .format(self.agent_name))

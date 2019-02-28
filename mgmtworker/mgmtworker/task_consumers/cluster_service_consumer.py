########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import logging

from cloudify.constants import CLUSTER_SERVICE_EXCHANGE_NAME
from cloudify.amqp_client import TaskConsumer
try:
    from cloudify_premium.ha import syncthing
except ImportError:
    update_devices = None

logger = logging.getLogger('mgmtworker')


class ClusterServiceConsumer(TaskConsumer):
    """
    This consumer is intended to be used only by the mgmtworker and only for
    cluster-related actions in a fanout-exchange type of communication
    """

    def __init__(self, queue_name, *args, **kwargs):
        super(ClusterServiceConsumer, self).__init__(queue_name,
                                                     exchange_type='fanout',
                                                     *args, **kwargs)
        self.queue = queue_name
        self.exchange = CLUSTER_SERVICE_EXCHANGE_NAME

        self.tasks_map = {
            'manager-added': self.manager_added,
            'manager-removed': self.manager_removed,
        }

    def handle_task(self, full_task):
        task = full_task['cluster_service_task']
        task_name = task['task_name']
        kwargs = task['kwargs']

        logger.info(
            'Received `{0}` cluster service task'.format(
                task_name
            )
        )
        result = self.tasks_map[task_name](**kwargs)
        logger.info('"{0}" Result: {1}'.format(task_name, result))

    def manager_added(self):
        logger.info('A manager has been added to the cluster, updating '
                    'Syncthing')
        syncthing.update_devices()

    def manager_removed(self):
        logger.info('A manager has been removed from the cluster, updating '
                    'Syncthing')
        syncthing.update_devices()

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

"""
Apply various mocks. this code is executed when the celery master first
launches, by including this file in the celery includes list
"""

from cloudify.exceptions import NonRecoverableError
from cloudify.utils import setup_logger
from cloudify.workflows import tasks


logger = setup_logger('testenv.mocks')


def task_exists(name, *args):
    logger.info('task_exists invoked with : {0}'
                .format(args))
    if 'non_existent' in name:
        logger.info('non_existent operation, raising NonRecoverableError')
        raise NonRecoverableError('non_existent operation [{0}]'.format(name))
    return True


# This is needed because in this
# environment, all tasks are sent to
# the management worker, and handled by
# different consumers. The original method
# asserts that tasks are being sent to
# different workers,
tasks.verify_task_registered = task_exists

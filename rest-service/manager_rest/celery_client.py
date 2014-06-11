########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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


__author__ = 'ran'


from celery import Celery
celery = Celery(broker='amqp://',
                backend='amqp://')

celery.conf.update(
    CELERY_TASK_SERIALIZER="json"
)


def execute_task(task_name, task_queue, task_id=None, kwargs=None):
    """
        Execute a task

        :param task_name: the task name
        :param task_queue: the task queue
        :param task_id: optional id for the task
        :param kwargs: optional kwargs to be passed to the task
        :return: the celery task async result
    """

    return celery.send_task(task_name,
                            queue=task_queue,
                            task_id=task_id,
                            kwargs=kwargs)

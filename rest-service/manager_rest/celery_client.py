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


from celery import Celery
from manager_rest import config

TASK_STATE_PENDING = 'PENDING'
TASK_STATE_STARTED = 'STARTED'
TASK_STATE_SUCCESS = 'SUCCESS'
TASK_STATE_RETRY = 'RETRY'
TASK_STATE_FAILURE = 'FAILURE'


class CeleryWrapper(Celery):

    def __enter__(self):
        self = super(CeleryWrapper, self).__enter__()
        self.conf.update(CELERY_TASK_SERIALIZER="json")
        return self


class CeleryClient(object):

    def __init__(self):
        """
            Instantiate CeleryClient instance with
            on-demand AMQP access connection

        """
        self.amqp_uri = 'amqp://{0}'.format(config.instance().amqp_address)

    def __enter__(self):
        self._current_instance = CeleryClient()
        return self._current_instance

    def __exit__(self, exc_type, exc_val, exc_tb):
        del self._current_instance

    def execute_task(self, task_name, task_queue, task_id=None, kwargs=None):
        """
            Execute a task

            :param task_name: the task name
            :param task_queue: the task queue
            :param task_id: optional id for the task
            :param kwargs: optional kwargs to be passed to the task
            :return: the celery task async result
        """

        with CeleryWrapper(broker=self.amqp_uri,
                           backend=self.amqp_uri) as cl:
            return cl.send_task(task_name,
                                queue=task_queue,
                                task_id=task_id,
                                kwargs=kwargs)

    def get_task_status(self, task_id):
        """
            Gets task's celery status by the task's id

            :param task_id: the task id
            :return: the task's celery status
        """
        with CeleryWrapper(broker=self.amqp_uri,
                           backend=self.amqp_uri) as cl:
            return cl.AsyncResult(task_id).status

    def get_failed_task_error(self, task_id):
        """
            Gets a failed task's error by the task's id

            :param task_id: the task id
            :return: the exception object
        """
        with CeleryWrapper(broker=self.amqp_uri,
                           backend=self.amqp_uri) as cl:
            return cl.AsyncResult(task_id).result


def celery_client():
    """
        Provides appropriate class for Celery workflow
        :return: Celery client
        :rtype CeleryClient
    """
    if config.instance().test_mode:
        from test.mocks import MockCeleryClient
        return MockCeleryClient
    else:
        return CeleryClient

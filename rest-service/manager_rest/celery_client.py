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

import ssl

from celery import Celery

from manager_rest import config

# These are the states that may be returned from the
# CeleryClient.get_task_status method
TASK_STATE_PENDING = 'PENDING'
TASK_STATE_STARTED = 'STARTED'
TASK_STATE_SUCCESS = 'SUCCESS'
TASK_STATE_RETRY = 'RETRY'
TASK_STATE_FAILURE = 'FAILURE'


class CeleryClient(object):

    def __init__(self):
        ssl_settings = self._get_broker_ssl_settings(
            ssl_enabled=config.instance.amqp_ssl_enabled,
            cert_path=config.instance.amqp_ca_path,
        )

        # Port not required as currently the address is provided with port and
        # vhost included.
        amqp_uri = 'amqp://{username}:{password}@{address}'.format(
            address=config.instance.amqp_address,
            username=config.instance.amqp_username,
            password=config.instance.amqp_password,
        )

        self.celery = Celery(broker=amqp_uri, backend=amqp_uri)
        self.celery.conf.update(
            CELERY_TASK_SERIALIZER="json",
            CELERY_TASK_RESULT_EXPIRES=600)
        if config.instance.amqp_ssl_enabled:
            self.celery.conf.update(BROKER_USE_SSL=ssl_settings)

    def close(self):
        if self.celery:
            self.celery.close()

    def execute_task(self, task_queue, task_id=None, kwargs=None):
        """
            Execute a task

            :param task_queue: the task queue
            :param task_id: optional id for the task
            :param kwargs: optional kwargs to be passed to the task
            :return: the celery task async result
        """

        return self.celery.send_task('cloudify.dispatch.dispatch',
                                     queue=task_queue,
                                     task_id=task_id,
                                     kwargs=kwargs)

    def get_task_status(self, task_id):
        """
            Gets task's celery status by the task's id

            :param task_id: the task id
            :return: the task's celery status
        """
        async_result = self.celery.AsyncResult(task_id)
        return async_result.status

    def get_failed_task_error(self, task_id):
        """
            Gets a failed task's error by the task's id

            :param task_id: the task id
            :return: the exception object
        """
        async_result = self.celery.AsyncResult(task_id)
        return async_result.result

    @staticmethod
    def _get_broker_ssl_settings(ssl_enabled, cert_path):
        # Input vars may be None if not set. Explicitly defining defaults.
        ssl_enabled = ssl_enabled or False
        cert_path = cert_path or ''

        if ssl_enabled:
            if not cert_path:
                raise ValueError(
                    "Broker SSL enabled but no SSL cert was provided. "
                    "If rabbitmq_ssl_enabled is True in the inputs, "
                    "rabbitmq_cert_public (and private) must be populated."
                )
            ssl_options = {
                'ca_certs': cert_path,
                'cert_reqs': ssl.CERT_REQUIRED,
            }
        else:
            ssl_options = {}

        return ssl_options


def get_client():
    if config.instance.test_mode:
        from test.mocks import MockCeleryClient
        return MockCeleryClient()
    else:
        return CeleryClient()

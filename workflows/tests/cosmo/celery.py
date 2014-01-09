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

from __future__ import absolute_import
from celery import Celery
from celery.signals import after_setup_task_logger
from cloudify.utils import build_includes
from os import path
import logging

__author__ = 'idanmo'


celery = Celery('cosmo.celery',
                broker='amqp://',
                backend='amqp://',
                include=build_includes(path.dirname(__file__)))

# Optional configuration, see the application user guide.
celery.conf.update(
    CELERY_TASK_SERIALIZER="json",
    CELERY_DEFAULT_QUEUE="cloudify.management"
)


@after_setup_task_logger.connect
def setup_logger(loglevel=None, **kwargs):
    logger = logging.getLogger("cosmo")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('| %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(loglevel)
        logger.propagate = True


if __name__ == '__main__':
    celery.start()

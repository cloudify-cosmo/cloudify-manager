#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

from __future__ import absolute_import
from celery import Celery
from celery.signals import after_setup_task_logger
from cosmo.events import send_log_event
import cosmo
import logging
import os
import json


class RiemannLoggingHandler(logging.Handler):
    """
    A Handler class for writing log messages to riemann.
    """
    def __init__(self):
        logging.Handler.__init__(self)

    def flush(self):
        pass

    def emit(self, record):
        message = self.format(record)
        log_record = {
            "name": record.name,
            "level": record.levelname,
            "message": message
        }
        try:
            send_log_event(log_record)
        except BaseException:
            pass

@after_setup_task_logger.connect
def setup_logger(loglevel=None, **kwargs):
    logger = logging.getLogger("cosmo")
    if not logger.handlers:
        handler = RiemannLoggingHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(loglevel)
        logger.propagate = True


def get_cosmo_properties():
    file_path = os.path.join(os.path.dirname(cosmo.__file__), 'cosmo.txt')
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.loads(f.read())
    # when on management machine, cosmo.txt does not exist so management_ip and ip are
    # pointing to the management machine which is localhost.
    return {
        'management_ip': 'localhost',
        'ip': 'localhost'
    }

celery = Celery('cosmo.celery',
                broker='amqp://',
                backend='amqp://')

# Optional configuration, see the application user guide.
celery.conf.update(
    CELERY_TASK_SERIALIZER="json"
)

if __name__ == '__main__':
    celery.start()

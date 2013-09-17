from __future__ import absolute_import
from celery import Celery
from cosmo import includes
from celery.signals import after_setup_task_logger
import logging

__author__ = 'idanmo'

celery = Celery('cosmo.celery',
                broker='amqp://',
                backend='amqp://',
                include=includes)

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
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(loglevel)
        logger.propagate = True


if __name__ == '__main__':
    celery.start()

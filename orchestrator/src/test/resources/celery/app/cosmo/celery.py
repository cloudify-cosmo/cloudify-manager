from __future__ import absolute_import

from celery import Celery

celery = Celery('cosmo.celery',
                broker='amqp://',
                backend='amqp://')

# Optional configuration, see the application user guide.
celery.conf.update(
    CELERY_TASK_SERIALIZER="json"
)

if __name__ == '__main__':
    celery.start()


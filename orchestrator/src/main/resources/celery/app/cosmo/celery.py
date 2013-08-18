import os
import cosmo

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

def get_management_ip():
    file_path = os.path.join(os.path.dirname(cosmo.__file__), 'management-ip.txt')
    with open(file_path, 'r') as f:
        return f.readlines()[0]

from __future__ import absolute_import

from celery import Celery

celery = Celery('cosmo.celery',
                broker='amqp://',
                backend='amqp://')

# Optional configuration, see the application user guide.
celery.conf.update(
    CELERY_TASK_SERIALIZER="json"
)

# Management machine, this is here as a work around due to import error because the plugin_installer is installed on
# management machine even though it doesn't need this. we should remove this once the plugin_installer wouldn't be
# installed on the management celery worker.
def get_management_ip():
    return "localhost"

if __name__ == '__main__':
    celery.start()

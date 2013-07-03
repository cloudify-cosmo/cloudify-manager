from __future__ import absolute_import

from celery import Celery
from cosmo import includes

celery = Celery('cosmo.celery')

# Optional configuration, see the application user guide.
celery.conf.update(
    CELERY_IMPORTS=','.join(includes)
)

if __name__ == '__main__':
    celery.start()


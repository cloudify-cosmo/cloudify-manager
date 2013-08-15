from __future__ import absolute_import

from celery import Celery
from cosmo import includes

celery = Celery('cosmo.celery',
                include=includes)

if __name__ == '__main__':
    celery.start()

from __future__ import absolute_import

from celery import Celery

celery = Celery('cosmo.celery')

if __name__ == '__main__':
    celery.start()


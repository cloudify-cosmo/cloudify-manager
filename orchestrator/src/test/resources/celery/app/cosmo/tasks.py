from __future__ import absolute_import

from cosmo.celery import celery


@celery.task
def add(x=None, y=None):
    return x + y


@celery.task
def fail():
    raise Exception()
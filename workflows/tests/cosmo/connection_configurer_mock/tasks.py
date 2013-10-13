from cosmo.celery import celery
from cosmo.persistency import Persist
from time import time

persist = Persist('connection_configurer')


@celery.task
def configure_connection(__cloudify_id, __relationship_cloudify_id, **kwargs):
    persist.write({
        'id': __cloudify_id,
        'relationship_id': __relationship_cloudify_id,
        'time': time(),
        'kwargs': kwargs
    })


@celery.task
def unconfigure_connection(__cloudify_id, __relationship_cloudify_id, **kwargs):
    pass


@celery.task
def get_state():
    return persist.read()
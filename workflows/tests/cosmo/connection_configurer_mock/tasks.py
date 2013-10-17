from cosmo.celery import celery
from cosmo.persistency import Persist
from time import time

persist = Persist('connection_configurer')


@celery.task
def configure_connection(__source_cloudify_id,
                         __target_cloudify_id,
                         __source_properties,
                         __target_properties,
                         **kwargs):
    persist.write({
        'source_id': __source_cloudify_id,
        'target_id': __target_cloudify_id,
        'time': time(),
        'source_properties': __source_properties,
        'target_properties': __target_properties
    })


@celery.task
def unconfigure_connection(__source_cloudify_id, __target_cloudify_id, **kwargs):
    pass


@celery.task
def get_state():
    return persist.read()
from cosmo.celery import celery
from cosmo.events import set_reachable as reachable
from cosmo.persistency import Persist
from time import time

persist = Persist('testmockoperations')


@celery.task
def make_reachable(__cloudify_id, **kwargs):
    reachable(__cloudify_id)
    persist.write({
        'id': __cloudify_id,
        'time': time()
    })


@celery.task
def get_state():
    return persist.read()
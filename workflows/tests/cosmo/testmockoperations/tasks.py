from cosmo.celery import celery
from cosmo.events import set_reachable as reachable
from cosmo.persistency import Persist
from time import time

persist = Persist('testmockoperations')

@celery.task
def make_reachable(__cloudify_id, **kwargs):
    reachable(__cloudify_id)
    try:
        state = persist.read()
    except BaseException:
        state = dict()
    state['id'] = __cloudify_id
    state['time'] = time()
    persist.write(state)


@celery.task
def touch(__cloudify_id, **kwargs):
    try:
        state = persist.read()
    except BaseException:
        state = dict()
    state['touched'] = True
    state['touched_time'] = time()
    persist.write(state)

@celery.task
def get_state():
    return persist.read()
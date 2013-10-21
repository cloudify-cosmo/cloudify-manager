from cosmo.celery import celery
from cosmo.events import set_reachable as reachable
from time import time

state = []

@celery.task
def make_reachable(__cloudify_id, **kwargs):
    reachable(__cloudify_id)
    global state
    state.append({
        'id': __cloudify_id,
        'time': time(),
        'relationships': kwargs['cloudify_runtime']
    })

@celery.task
def get_state():
    return state

from cosmo.celery import celery
from cosmo.events import set_reachable as reachable
from time import time

state = []
touched_time = None


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
def touch(**kwargs):
    global touched_time
    touched_time = time()


@celery.task
def get_state():
    return state


@celery.task
def get_touched_time():
    return touched_time

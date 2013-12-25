from cosmo.celery import celery
from cosmo.events import set_reachable as reachable
from cosmo.events import set_unreachable as unreachable
from cosmo.events import set_property as property
from time import time

state = []
touched_time = None
unreachable_call_order = []


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
def make_unreachable(__cloudify_id, **kwargs):
    unreachable(__cloudify_id)
    global unreachable_call_order
    unreachable_call_order.append({
        'id': __cloudify_id,
        'time': time()
    })


@celery.task
def set_property(__cloudify_id, property_name, value, **kwargs):
    property(__cloudify_id, property_name, value)


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

@celery.task
def is_unreachable_called(__cloudify__id, **kwargs):
    return next((x for x in unreachable_call_order if x['id'] == __cloudify__id), None)

@celery.task
def get_unreachable_call_order():
    return unreachable_call_order
from cosmo.celery import celery
from time import time

state = []


@celery.task
def configure_connection(**kwargs):
    append_to_state(**kwargs)


@celery.task
def unconfigure_connection(**kwargs):
    append_to_state(**kwargs)


def append_to_state(__source_cloudify_id,
                    __target_cloudify_id,
                    __run_on_node_cloudify_id,
                    __source_properties,
                    __target_properties,
                    **kwargs):
    global state
    state.append({
        'source_id': __source_cloudify_id,
        'target_id': __target_cloudify_id,
        'time': time(),
        'source_properties': __source_properties,
        'target_properties': __target_properties,
        'run_on_node_id': __run_on_node_cloudify_id
    })


@celery.task
def get_state():
    return state

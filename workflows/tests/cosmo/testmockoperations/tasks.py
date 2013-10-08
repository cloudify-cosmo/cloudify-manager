from cosmo.celery import celery
from cosmo.events import set_reachable as reachable
from cosmo.persistency import Persist

persist = Persist('testmockoperations')


@celery.task
def make_reachable(__cloudify_id, **kwargs):
    reachable(__cloudify_id)
    persist.write(__cloudify_id)

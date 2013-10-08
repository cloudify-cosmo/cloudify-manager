from cosmo.celery import celery
from cosmo.persistency import Persist


persist = Persist('connection_configurer')


@celery.task
def configure_connection(__cloudify_id, **kwargs):
    persist.write(__cloudify_id)


@celery.task
def unconfigure_connection(__cloudify_id, **kwargs):
    pass



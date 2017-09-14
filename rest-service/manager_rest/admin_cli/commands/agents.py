
from .. import acfy, exceptions
from manager_rest import celery_client


MGMTWORKER_NAME = 'cloudify.management'


@acfy.group(name='agents')
def agents():
    """Handle agents connected to the Manager
    """
    pass


@agents.command('list')
@acfy.pass_logger
def agents_list(logger):
    client = celery_client.get_client()
    try:
        registered = client.celery.control.inspect().registered()
    except TypeError:  # in case control, or inspect is None - not connected
        raise exceptions.CloudifyACliError(
            'Unable to get connected RabbitMQ clients')

    for name in registered:
        worker, _, host = name.partition('@')
        if host == MGMTWORKER_NAME:
            continue
        logger.info(host)

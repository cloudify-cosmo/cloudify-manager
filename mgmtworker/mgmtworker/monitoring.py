import logging
logger = logging.getLogger('mgmtworker')


def manager_added(rest_client=None):
    manager_client = rest_client.manager
    logger.info('ManagerClient (%s): %s', type(manager_client), manager_client)
    for manager in manager_client.get_managers().items:
        logger.info('Manager in DB: ', manager)
    return "MANAGER is {0}:\n{1}\n".format(
        type(manager_client), manager_client)


def manager_removed():
    pass


def _render_other_managers(ip_addresses):
    pass

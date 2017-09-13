from .. import acfy, exceptions
try:
    from cloudify_premium.ha import cluster_status
except ImportError:
    cluster_status = None


@acfy.group(name='cluster')
def cluster():
    if cluster_status is None:
        raise exceptions.CloudifyACliError('This feature is not available')


@cluster.group(name='settings')
def settings():
    pass


def _get_cluster_settings(logger):
    for name, value in cluster_status.cluster_options.items():
        logger.info('{0}: {1}'.format(name, value))


def _get_node_settings(node_name, logger):
    logger.info('Options for node {0}:'.format(node_name))
    for name, value in cluster_status.node_options.get(node_name, {}).items():
        logger.info('{0}: {1}'.format(name, value))


@settings.command(name='get')
@acfy.options.node_name
@acfy.pass_logger
def get_settings(node_name, logger):
    if node_name:
        _get_node_settings(node_name, logger)
    else:
        _get_cluster_settings(logger)

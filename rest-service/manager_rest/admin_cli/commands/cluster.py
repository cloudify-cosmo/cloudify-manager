
import requests

from functools import wraps

from .. import acfy, exceptions

try:
    from cloudify_premium.ha import cluster_status, commands
except ImportError:
    cluster_status = None


def _validate_cluster(f):
    @wraps(f)
    def _inner(*args, **kwargs):
        try:
            if len(cluster_status.nodes) < 1:
                raise ValueError('No cluster nodes')
        except Exception:
            raise exceptions.CloudifyACliError('Cluster has not been started')
        return f(*args, **kwargs)
    return _inner


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
@_validate_cluster
def get_settings(node_name, logger):
    if node_name:
        _get_node_settings(node_name, logger)
    else:
        _get_cluster_settings(logger)


@cluster.command(name='start')
@acfy.options.node_name
@acfy.options.host_ip
@acfy.pass_context
def start(ctx, host_ip, node_name):
    ctx.invoke(commands.create_cluster_node, config={
        'host_ip': host_ip,
        'node_name': node_name,
        'bootstrap_cluster': True
    })


@cluster.command(name='join')
@acfy.options.node_name
@acfy.options.host_ip
@acfy.options.master_ip
@acfy.options.manager_username
@acfy.options.manager_password
@acfy.pass_context
def join(ctx, host_ip, node_name, master_ip, manager_username,
         manager_password):
    protocol = 'http'
    data = {'host_ip': host_ip, 'node_name': node_name}
    response = requests.put('{0}://{1}/api/v3/cluster/nodes/{2}'
                            .format(protocol, master_ip, node_name),
                            verify=False, json=data,
                            auth=(manager_username, manager_password))
    response_data = response.json()
    credentials = response_data['credentials']
    ctx.invoke(commands.create_cluster_node, config={
        'host_ip': host_ip,
        'node_name': node_name,
        'bootstrap_cluster': False,
        'credentials': credentials,
        'join_addrs': [master_ip]
    })

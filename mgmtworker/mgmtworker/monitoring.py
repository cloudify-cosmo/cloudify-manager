import json

from os import sep
from os.path import join

from cloudify.utils import get_manager_name, setup_logger

logger = setup_logger('cloudify.monitoring')

PROMETHEUS_CONFIG_DIR = join(sep, 'etc', 'prometheus', )
PROMETHEUS_TARGETS_DIR = join(PROMETHEUS_CONFIG_DIR, 'targets')
PROMETHEUS_TARGETS_TEMPLATE = '- targets: {target_addresses}\n'\
                              '  labels: {target_labels}'


def update_manager_targets(rest_client):
    """Update other managers in Prometheus target file."""
    manager_targets = []
    for private_ip in _other_managers_private_ips(rest_client.manager):
        manager_targets.append('{0}:8009'.format(private_ip))
    logger.info('Other managers will be monitored: %s', manager_targets)
    file_name = _deploy_prometheus_targets('other_managers.yml',
                                           manager_targets, {})
    logger.debug('Prometheus configuration successfully deployed: %s',
                 file_name)


def update_broker_targets(rest_client):
    """Update other rabbits in Prometheus target file."""
    rabbit_targets = []
    for private_ip in _other_rabbits_private_ips(rest_client.manager):
        rabbit_targets.append('{0}:8009'.format(private_ip))
    logger.info('Other rabbits will be monitored: %s', rabbit_targets)
    file_name = _deploy_prometheus_targets('other_rabbits.yml',
                                           rabbit_targets, {})
    logger.debug('Prometheus configuration successfully deployed: %s',
                 file_name)


def update_db_targets(rest_client):
    """Update other postgtres in Prometheus target file."""
    postgres_targets = []
    for private_ip in _other_postgres_private_ips(rest_client.manager):
        postgres_targets.append('{0}:8009'.format(private_ip))
    logger.info('Other postgres will be monitored: %s', postgres_targets)
    file_name = _deploy_prometheus_targets('other_postgres.yml',
                                           postgres_targets, {})
    logger.debug('Prometheus configuration successfully deployed: %s',
                 file_name)


def _other_managers_private_ips(manager_client):
    """Generate other managers' private_ips."""
    my_hostname = get_manager_name()
    for manager in manager_client.get_managers():
        if not _matches_my_hostname(manager['hostname'], my_hostname):
            yield manager['private_ip']


def _other_rabbits_private_ips(manager_client):
    """Generate other brokers' private_ips."""
    my_hostname = get_manager_name()
    for broker in manager_client.get_brokers():
        if not _matches_my_hostname(broker['name'], my_hostname):
            yield broker['host']


def _other_postgres_private_ips(manager_client):
    """Generate other postgres' private_ips."""
    my_hostname = get_manager_name()
    for db_node in manager_client.get_db_nodes():
        if not _matches_my_hostname(db_node['name'], my_hostname):
            yield db_node['host']


def _matches_my_hostname(a_hostname, my_hostname=None):
    if my_hostname is None:
        my_hostname = get_manager_name()
    if '.' in a_hostname and '.' in my_hostname:
        return a_hostname == my_hostname
    return a_hostname.split('.')[0] == my_hostname.split('.')[0]


def _deploy_prometheus_targets(destination, targets, labels):
    """Deploy a target file for prometheus.
    :param destination: Target file name in targets dir.
    :param targets: List of targets for prometheus.
    :param labels: Dict of labels with values for prometheus."""
    return _render_template(
        PROMETHEUS_TARGETS_TEMPLATE,
        join(PROMETHEUS_TARGETS_DIR, destination),
        target_addresses=json.dumps(targets),
        target_labels=json.dumps(labels),
    )


def _render_template(template, destination, **kwargs):
    """Render a template into a file destination.
    :param template: A text template to be rendered
    :param destination: Destination file name.
    :param kwargs: Arguments for the template render."""
    content = template.format(**kwargs)
    with open(destination, 'w') as f:
        f.write(content)
    return destination

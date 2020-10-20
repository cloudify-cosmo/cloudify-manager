import json
import tempfile

from os import rename, sep
from os.path import join

from cloudify.utils import get_manager_name, setup_logger

logger = setup_logger('cloudify.monitoring')

PRIVATE_IP = 'private_ip'
HOSTNAME = 'hostname'
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


def _other_managers_private_ips(manager_client):
    """Generate other managers' private_ips."""
    my_hostname = get_manager_name()
    for manager in manager_client.get_managers():
        if manager[HOSTNAME] != my_hostname:
            yield manager[PRIVATE_IP]


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
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(content)
    rename(f.name, destination)
    return destination

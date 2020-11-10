from os import kill, rename, sep
from os.path import join
from signal import SIGHUP
from subprocess import check_output

import json
import re
import yaml

from jinja2 import Template
from tempfile import NamedTemporaryFile

from cloudify.utils import setup_logger

logger = setup_logger('cloudify.monitoring')

PROMETHEUS_CONFIG_DIR = join(sep, 'etc', 'prometheus', )
PROMETHEUS_TARGETS_DIR = join(PROMETHEUS_CONFIG_DIR, 'targets')
PROMETHEUS_ALERTS_DIR = join(PROMETHEUS_CONFIG_DIR, 'alerts')
PROMETHEUS_TARGETS_TEMPLATE = '- targets: {target_addresses}\n'\
                              '  labels: {target_labels}'
PROMETHEUS_MISSING_ALERT = Template(
    """groups:
  - name: {{ name }}
    rules:{% for host in hosts %}
      - alert: {{ name }}_missing
        expr: absent({{ name }}_healthy{host="{{ host }}"})
        for: {{ alert_for }}
        labels:
          severity: critical
        annotations:
          summary: "{{ name|capitalize }} is missing on node {{ host }}"

      - alert: prometheus_missing
        expr: absent(up{host="{{ host }}", job="prometheus"})
        for: {{ alert_for }}
        labels:
          severity: critical
        annotations:
          summary: "Prometheus is missing on node {{ host }}"
{% endfor %}""")


def get_manager_hosts(manager_client):
    """Generate other managers' private_ips."""
    for manager in manager_client.get_managers():
        yield manager['private_ip']


def get_broker_hosts(manager_client):
    """Generate other brokers' private_ips."""
    for broker in manager_client.get_brokers():
        yield broker['host']


def get_db_hosts(manager_client):
    """Generate other postgres' private_ips."""
    for db_node in manager_client.get_db_nodes():
        yield db_node['host']


def update_manager_targets(hosts):
    """Update other managers in Prometheus target file."""
    manager_targets = ['{0}:8009'.format(host) for host in hosts]
    logger.info('Other managers will be monitored: %s', manager_targets)
    file_name = _deploy_prometheus_targets('other_managers.yml',
                                           manager_targets)
    logger.debug('Prometheus configuration successfully deployed: %s',
                 file_name)


def update_broker_targets(hosts):
    """Update other rabbits in Prometheus target file."""
    rabbit_targets = ['{0}:8009'.format(host) for host in hosts]
    logger.info('Other rabbits will be monitored: %s', rabbit_targets)
    file_name = _deploy_prometheus_targets('other_rabbits.yml',
                                           rabbit_targets)
    logger.debug('Prometheus configuration successfully deployed: %s',
                 file_name)


def update_db_targets(hosts):
    """Update other postgtres in Prometheus target file."""
    postgres_targets = ['{0}:8009'.format(host) for host in hosts]
    logger.info('Other postgres will be monitored: %s', postgres_targets)
    file_name = _deploy_prometheus_targets('other_postgres.yml',
                                           postgres_targets)
    logger.debug('Prometheus configuration successfully deployed: %s',
                 file_name)


def update_manager_alerts(hosts):
    """Update Prometheus alerts for cluster managers."""
    logger.info('Generating alerts for managers: %s', hosts)
    file_name = _deploy_prometheus_missing_alerts('manager_missing.yml',
                                                  'manager',
                                                  hosts)
    _reload_prometheus()
    logger.debug('Prometheus alerts successfully deployed: %s', file_name)


def update_broker_alerts(hosts):
    """Update Prometheus alerts for cluster broker nodes."""
    logger.info('Generating alerts for rabbits: %s', hosts)
    file_name = _deploy_prometheus_missing_alerts('rabbitmq_missing.yml',
                                                  'rabbitmq',
                                                  hosts)
    _reload_prometheus()
    logger.debug('Prometheus alerts successfully deployed: %s', file_name)


def update_db_alerts(hosts):
    """Update Prometheus alerts for cluster db nodes."""
    logger.info('Generating alerts for postgres: %s', hosts)
    file_name = _deploy_prometheus_missing_alerts('postgres_missing.yml',
                                                  'postgres',
                                                  hosts)
    _reload_prometheus()
    logger.debug('Prometheus alerts successfully deployed: %s', file_name)


def _deploy_prometheus_targets(destination, targets, labels=None):
    """Deploy a target file for prometheus.
    :param destination: Target file name in targets dir.
    :param targets: List of targets for prometheus.
    :param labels: Dict of labels with values for prometheus."""
    labels = labels or {}
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


def _deploy_prometheus_missing_alerts(destination, service_name, hosts):
    prometheus_config = _read_prometheus_yml()
    scrape_interval = prometheus_config.get('global', {}).\
        get('scrape_interval', '15s')
    template = PROMETHEUS_MISSING_ALERT.render(
        name=service_name,
        hosts=hosts,
        alert_for=_calculate_alert_for(scrape_interval))
    with NamedTemporaryFile(mode='w+t', delete=False) as f:
        f.write(template)
        tmp_file_name = f.name
    rename(tmp_file_name,
           join(PROMETHEUS_ALERTS_DIR, destination))
    return destination


def _calculate_alert_for(scrape_interval):
    if scrape_interval:
        scrape_interval = '{0}'.format(scrape_interval).lower()
    m = re.match(r'^((\d+)s)?((\d+)ms)?', scrape_interval)
    if not m or not m.lastindex or m.lastindex < 1:
        return '15s'
    scrape_seconds = int(m[2] or 0) + 0.001 * int(m[4] or 0)
    if scrape_seconds >= 15.0:
        return '15s'
    else:
        return m[0]


def _read_prometheus_yml(config_file_name='/etc/prometheus/prometheus.yml'):
    with open(config_file_name, 'r') as config_file:
        try:
            return yaml.safe_load(config_file)
        except yaml.YAMLError as ex:
            logger.exception('Error reading Prometheus configuration')
            raise ex


def _reload_prometheus():
    # Send SIGHUP to the prometheus process to reload alerts configuration
    pid = int(check_output(['pidof', 'prometheus']).strip())
    logger.info('Reloading the Prometheus ({0}) configuration'.format(pid))
    kill(pid, SIGHUP)

import threading
import queue
from datetime import datetime

from flask import current_app

from cloudify.cluster_status import (ServiceStatus,
                                     CloudifyNodeType,
                                     NodeServiceStatus)

from manager_rest.config import instance as config
from manager_rest.prometheus_client import query as prometheus_query
from manager_rest.storage import models, get_storage_manager


STATUS = 'status'

SERVICE_DESCRIPTIONS = {
    'blackbox_exporter': {
        'name': 'Blackbox Exporter',
        'description': 'Prometheus blackbox exporter (HTTP/HTTPS/TCP pings}'},
    'cloudify-amqp-postgres': {
        'name': 'AMQP-Postgres',
        'description': 'Cloudify AMQP PostgreSQL Broker service'},
    'cloudify-composer': {
        'name': 'Cloudify Composer',
        'description': 'Cloudify Composer service'},
    'cloudify-mgmtworker': {
        'name': 'Management Worker',
        'description': 'Cloudify Management Worker service'},
    'cloudify-rabbitmq': {
        'name': 'RabbitMQ Broker',
        'description': 'RabbitMQ Broker service'},
    'cloudify-restservice': {
        'name': 'Manager REST',
        'description': 'Cloudify REST service'},
    'cloudify-stage': {
        'name': 'Cloudify Console',
        'description': 'Cloudify Console service'},
    'cloudify-syncthing': {
        'name': 'Syncthing',
        'description': 'Syncthing service'},
    'etcd': {
        'name': 'Etcd key-value store',
        'description': 'Etcd distributed key-value store service'},
    'haproxy': {
        'name': 'HA Proxy',
        'description': 'HAProxy Load Balancer service'},
    'nginx': {
        'name': 'Webserver',
        'description': 'nginx - high performance web server'},
    'node_exporter': {
        'name': 'Node Exporter',
        'description': 'Prometheus exporter for hardware and OS metrics'},
    'patroni': {
        'name': 'Patroni HA Template',
        'description': 'Patroni HA Template service'},
    'postgresql-9.5': {
        'name': 'PostgreSQL 9.5 database server',
        'description': 'PostgreSQL 9.5 database server'},
    'postgres_exporter': {
        'name': 'Prometheus exporter for PostgreSQL',
        'description': 'Prometheus exporter for PostgreSQL service'},
    'prometheus': {
        'name': 'Prometheus',
        'description': 'Prometheus monitoring service'},
}
SERVICE_ASSIGNMENTS = {
    CloudifyNodeType.DB: [
        'etcd',
        'nginx',
        'node_exporter',
        'patroni',
        'postgres_exporter',
        'postgresql-9.5',
        'prometheus',
    ],
    CloudifyNodeType.BROKER: [
        'cloudify-rabbitmq',
        'nginx',
        'node_exporter',
        'prometheus',
    ],
    CloudifyNodeType.MANAGER: [
        'blackbox_exporter',
        'cloudify-amqp-postgres',
        'cloudify-composer',
        'cloudify-mgmtworker',
        'cloudify-restservice',
        'cloudify-stage',
        'cloudify-syncthing',
        'haproxy',
        'nginx',
        'node_exporter',
        'prometheus',
    ]
}

QUERY_STRINGS = {
    CloudifyNodeType.DB:
        '(up{job=~".*postgresql"} == 1 and pg_up{job=~".*postgresql"} == 1)',
    CloudifyNodeType.BROKER: '(up{job=~".*rabbitmq"})',
    CloudifyNodeType.MANAGER: '(probe_success{job=~".*http_.+"})',
}


def get_cluster_status(detailed=False):
    cluster_nodes, cloudify_version = _get_cluster_details()
    _add_monitoring_data(cluster_nodes)

    cluster_status = {
        'services': {
            CloudifyNodeType.BROKER: _get_broker_state(cluster_nodes,
                                                       cloudify_version,
                                                       detailed),
            CloudifyNodeType.DB: _get_db_state(cluster_nodes,
                                               cloudify_version,
                                               detailed),
            CloudifyNodeType.MANAGER: _get_manager_state(cluster_nodes,
                                                         cloudify_version,
                                                         detailed),
        },
    }
    cluster_status['status'] = _get_overall_state(cluster_status)

    return cluster_status


class ConcurrentStatusChecker(object):
    def __init__(self):
        self._in_queue = queue.Queue()
        self._out_queue = queue.Queue()
        self._threads = None

    def _worker(self):
        while True:
            address, details = self._in_queue.get()

            query_parts = [
                QUERY_STRINGS[service_type]
                for service_type in details['services']
            ]
            query_parts.extend([
                'node_systemd_unit_state{state="active"}',
                'node_supervisord_up',
            ])

            query_string = ' or '.join(query_parts)

            try:
                prometheus_response = prometheus_query(
                    'https://{}:8009/monitoring/'.format(address),
                    query_string=query_string,
                    auth=(details['username'], details['password']),
                    ca_path=details['ca_path'],
                    timeout=config.monitoring_timeout,
                )
            except Exception:
                # TODO: Log!
                self._out_queue.put((address, [],))
            else:
                self._out_queue.put((address,
                                     prometheus_response,))

    def _initialize_threads(self, number_of_threads):
        self._threads = [
            threading.Thread(target=self._worker)
            for _ in range(number_of_threads)
        ]
        for thread in self._threads:
            thread.daemon = True
            thread.start()

    def get(self, cluster_nodes):
        if self._threads is None:
            self._initialize_threads(len(cluster_nodes))
        result = {}
        for address, details in cluster_nodes.items():
            result[address] = None
            self._in_queue.put((address, details))
        for _ in range(len(result)):
            try:
                address, prometheus_response = self._out_queue.get(
                    timeout=config.monitoring_timeout + 1)
            except queue.Empty:
                pass
            else:
                result[address] = prometheus_response
        return result


def get_concurrent_status_checker():
    if not hasattr(current_app, 'concurrent_status_checker'):
        current_app.concurrent_status_checker = ConcurrentStatusChecker()
    return current_app.concurrent_status_checker


def _add_monitoring_data(cluster_nodes):
    # We should try to make this be something that we just retrieve
    # from the local (federated) prometheus, but we're not there yet
    status_getter = get_concurrent_status_checker()
    for address, results in status_getter.get(cluster_nodes).items():
        results = [
            metric for metric in results
            if 'federate' not in metric.get('metric', {}).get('job', '')
        ]
        service_results, metric_results = _parse_prometheus_results(results)

        cluster_nodes[address]['service_results'] = service_results
        cluster_nodes[address]['metric_results'] = metric_results


def _get_cluster_details():
    storage_manager = get_storage_manager()
    cluster_services = {
        CloudifyNodeType.MANAGER: storage_manager.list(models.Manager),
        CloudifyNodeType.DB: storage_manager.list(models.DBNodes),
        CloudifyNodeType.BROKER: storage_manager.list(models.RabbitMQBroker),
    }

    ca_paths = {
        CloudifyNodeType.DB: config.postgresql_ca_cert_path,
        CloudifyNodeType.BROKER: config.amqp_ca_path,
        CloudifyNodeType.MANAGER: config.ca_cert_path,
    }

    mapping = {}
    version = None

    for service_type, nodes in cluster_services.items():
        for node in nodes:
            if service_type == CloudifyNodeType.MANAGER and not version:
                version = node.version
            if node.private_ip not in mapping:
                mapping[node.private_ip] = {
                    'username': node.monitoring_username,
                    'password': node.monitoring_password,
                    'ca_path': ca_paths[service_type],
                    'node_name': node.name,
                    'public_ip': node.public_ip,
                    'private_ip': node.private_ip,
                    'services': [],
                    'external_services': [],
                    'service_results': [],
                    'metric_results': {},
                }

            target = 'external_services' if node.is_external else 'services'
            mapping[node.private_ip][target].append(service_type)
    return mapping, version


def _get_broker_state(cluster_nodes, cloudify_version, detailed):
    return _get_cluster_service_state(
        cluster_nodes,
        cloudify_version,
        detailed,
        CloudifyNodeType.BROKER,
    )


def _get_db_state(cluster_nodes, cloudify_version, detailed):
    return _get_cluster_service_state(
        cluster_nodes,
        cloudify_version,
        detailed,
        CloudifyNodeType.DB,
    )


def _get_manager_state(cluster_nodes, cloudify_version, detailed):
    return _get_cluster_service_state(
        cluster_nodes,
        cloudify_version,
        detailed,
        CloudifyNodeType.MANAGER,
    )


def _get_cluster_service_state(cluster_nodes, cloudify_version, detailed,
                               service_type):
    is_external = _is_external(cluster_nodes, service_type)

    state = {
        'is_external': is_external,
    }

    if is_external:
        state['status'] = ServiceStatus.HEALTHY
        return state

    service_nodes = _get_nodes_of_type(cluster_nodes, service_type)

    nodes = {
        service_node['node_name']: {
            'private_ip': service_node['private_ip'],
            'public_ip': service_node['public_ip'],
            'version': cloudify_version,
            'services': [
                service for service in service_node['service_results']
                if _service_expected(service, service_type)
            ],
            'metrics': service_node['metric_results'].get(service_type,
                                                          []),
        }
        for service_node in service_nodes.values()
    }

    node_count = len(nodes)

    if service_type == CloudifyNodeType.DB:
        if node_count > 1:
            # This is a cluster, remove the postgresql service if present, as
            # patroni will manage it and it will just cause incorrect errors
            for node in nodes.values():
                pg_idx = None
                for idx, svc in enumerate(node['services']):
                    if _get_unit_id(svc).startswith(
                        'postgresql'
                    ):
                        pg_idx = idx
                        break
                if pg_idx is not None:
                    node['services'].pop(pg_idx)

    for node in nodes.values():
        node['status'] = _get_node_state(node)

    for node in nodes.values():
        node['status'] = _get_node_state(node)

    if service_type == CloudifyNodeType.MANAGER:
        quorum = 1
    else:
        quorum = (node_count // 2) + 1

    state['status'] = _get_cluster_service_status(
        nodes=nodes, quorum=quorum,
    )

    if not detailed:
        for node in nodes.values():
            node.pop('services')
            node.pop('metrics')

    state['nodes'] = nodes

    return state


def _get_cluster_service_status(nodes, quorum):
    healthy_nodes_count = len([
        node for node in nodes.values()
        if node['status'] == ServiceStatus.HEALTHY
    ])

    if healthy_nodes_count == len(nodes):
        return ServiceStatus.HEALTHY
    elif healthy_nodes_count >= quorum:
        return ServiceStatus.DEGRADED
    else:
        return ServiceStatus.FAIL


def _get_overall_state(cluster_status):
    found_degraded = False

    for service in cluster_status['services'].values():
        if service['status'] == ServiceStatus.FAIL:
            return ServiceStatus.FAIL
        elif service['status'] == ServiceStatus.DEGRADED:
            found_degraded = True

    return ServiceStatus.DEGRADED if found_degraded else ServiceStatus.HEALTHY


def _get_unit_id(service):
    if 'systemd' in service['extra_info']:
        return service['extra_info']['systemd']['unit_id']
    else:
        return service['extra_info']['supervisord']['unit_id']


def _service_expected(service, service_type):
    unit_id = _get_unit_id(service)
    if unit_id.endswith('.service'):
        unit_id = unit_id[:-len('.service')]
    return unit_id in SERVICE_ASSIGNMENTS[service_type]


def _get_nodes_of_type(cluster_nodes, service_type):
    requested_nodes = {}
    for node, details in cluster_nodes.items():
        if service_type in details['services']:
            requested_nodes[node] = details
    return requested_nodes


def _is_external(cluster_nodes, service_type):
    for node_details in cluster_nodes.values():
        if service_type in node_details['external_services']:
            return True
    return False


def _get_node_state(node):
    if not node['services'] or not node['metrics']:
        # Absence of failure (and everything else) is not success
        return ServiceStatus.FAIL

    for service in node['services']:
        if service['status'] != NodeServiceStatus.ACTIVE:
            return ServiceStatus.FAIL

    for metric in node['metrics']:
        if not metric['healthy']:
            return ServiceStatus.FAIL

    return ServiceStatus.HEALTHY


def _parse_prometheus_results(prometheus_results):
    service_results = []
    metric_results = {}

    for result in prometheus_results:
        metric = result.get('metric', {})
        # Technically the second element in the tuple is the metric value, but
        # we only use it to indicate health currently
        timestamp, healthy = result.get('value', [0, ''])
        healthy = healthy == '1'

        process_manager = None
        if metric.get('__name__') == 'node_systemd_unit_state':
            process_manager = 'systemd'
        elif metric.get('__name__') == 'node_supervisord_up':
            process_manager = 'supervisord'

        if process_manager:
            service_id = metric.get('name', '')
            service = _get_cloudify_service_description(service_id)

            # Only process services we care about
            if service:
                service_results.append(_get_service_status(
                    service_id=service_id,
                    service=service,
                    process_manager=process_manager,
                    is_running=healthy,
                ))
        else:
            if metric.get('job'):
                processed_data, service_type = _process_metric(
                    metric, timestamp, healthy)
                if service_type not in metric_results:
                    metric_results[service_type] = []
                metric_results[service_type].append(processed_data)
            else:
                # TODO: Log something
                pass
    return service_results, metric_results


def _get_service_status(service_id, service, process_manager, is_running):
    return {
        'status': (NodeServiceStatus.ACTIVE if is_running
                   else NodeServiceStatus.INACTIVE),
        'extra_info': {
            process_manager: {
                'instances': [
                    {
                        'Description': service['description'],
                        'state': ('running' if is_running else 'stopped'),
                        'Id': service_id,
                    },
                ],
                'display_name': service['name'],
                'unit_id': service_id,
            },
        },
    }


def _process_metric(metric, timestamp, healthy):
    job = metric.get('job', '')

    if job.endswith('postgresql'):
        service_type = CloudifyNodeType.DB
    elif job.endswith('rabbitmq'):
        service_type = CloudifyNodeType.BROKER
    else:
        service_type = CloudifyNodeType.MANAGER

    if timestamp:
        last_check = datetime.fromtimestamp(timestamp).strftime(
            '%Y-%m-%dT%H:%M:%S.%fZ',
        )
    else:
        last_check = 'unknown'

    metric_name = job
    if metric.get('instance'):
        metric_name += ' on {}'.format(metric.get('instance'))

    return {
        'last_check': last_check,
        'healthy': healthy,
        'metric_type': metric.get('__name__', 'unknown'),
        'metric_name': metric_name,
    }, service_type


def _get_cloudify_service_description(metric_name):
    if metric_name in SERVICE_DESCRIPTIONS:
        return SERVICE_DESCRIPTIONS[metric_name]
    elif metric_name.endswith('.service'):
        return _get_cloudify_service_description(metric_name[:-8])
    return None

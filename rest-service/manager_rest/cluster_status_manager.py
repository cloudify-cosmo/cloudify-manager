from datetime import datetime
import typing

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
        'description': 'AMQP PostgreSQL Broker service'},
    'cloudify-composer': {
        'name': 'Composer',
        'description': 'Composer service'},
    'cloudify-mgmtworker': {
        'name': 'Management Worker',
        'description': 'Management Worker service'},
    'cloudify-rabbitmq': {
        'name': 'RabbitMQ Broker',
        'description': 'RabbitMQ Broker service'},
    'cloudify-restservice': {
        'name': 'Manager REST',
        'description': 'REST API service'},
    'cloudify-stage': {
        'name': 'Management Console',
        'description': 'Management Console service'},
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
    CloudifyNodeType.DB: '(postgres_healthy) or (postgres_service)',
    CloudifyNodeType.BROKER: '(rabbitmq_healthy) or (rabbitmq_service)',
    CloudifyNodeType.MANAGER: '(manager_healthy) or (manager_service)',
}


def get_cluster_status(detailed=False) -> typing.Dict[str, typing.Any]:
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


def _add_monitoring_data(cluster_nodes: typing.Dict[str, dict]) -> None:
    """Add metrics data and information on services for the cluster nodes."""
    query_string = ' or '.join(QUERY_STRINGS.values())
    global_results = prometheus_query(
        query_string=query_string,
        logger=current_app.logger,
        timeout=config.monitoring_timeout,
    )

    unexpected_metrics = [
        result for result in global_results
        if not _host_matches(result.get('metric'), cluster_nodes.keys())
    ]
    if unexpected_metrics:
        current_app.logger.warning(
            'These metrics do not match monitored IP address%s (%s): %s',
            '' if len(cluster_nodes) == 1 else 'es',
            ', '.join(cluster_nodes.keys()),
            unexpected_metrics,
        )

    for address in cluster_nodes.keys():
        service_results, metric_results = _parse_prometheus_results([
            result for result in global_results
            if 'metrics' in result
               and _host_matches(result.get('metric'), [address])
        ])
        cluster_nodes[address]['service_results'] = service_results
        cluster_nodes[address]['metric_results'] = metric_results


def _get_cluster_details() -> typing.Tuple[typing.Dict[str, dict], str]:
    storage_manager = get_storage_manager()
    cluster_services = {
        CloudifyNodeType.MANAGER: storage_manager.list(models.Manager),
        CloudifyNodeType.DB: storage_manager.list(models.DBNodes),
        CloudifyNodeType.BROKER: storage_manager.list(models.RabbitMQBroker),
    }

    mapping = {}
    version = None

    for service_type, nodes in cluster_services.items():
        for node in nodes:
            if service_type == CloudifyNodeType.MANAGER and not version:
                version = node.version
            if node.private_ip not in mapping:
                mapping[node.private_ip] = {
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
    return mapping, version or 'UNKNOWN'


def _get_broker_state(cluster_nodes: typing.Dict[str, dict],
                      cloudify_version: str,
                      detailed: bool) -> typing.Dict[str, typing.Any]:
    return _get_cluster_service_state(
        cluster_nodes,
        cloudify_version,
        detailed,
        CloudifyNodeType.BROKER,
    )


def _get_db_state(cluster_nodes: typing.Dict[str, dict],
                  cloudify_version: str,
                  detailed: bool) -> typing.Dict[str, typing.Any]:
    return _get_cluster_service_state(
        cluster_nodes,
        cloudify_version,
        detailed,
        CloudifyNodeType.DB,
    )


def _get_manager_state(cluster_nodes: typing.Dict[str, dict],
                       cloudify_version: str,
                       detailed: bool) -> typing.Dict[str, typing.Any]:
    return _get_cluster_service_state(
        cluster_nodes,
        cloudify_version,
        detailed,
        CloudifyNodeType.MANAGER,
    )


def _get_cluster_service_state(cluster_nodes: typing.Dict[str, dict],
                               cloudify_version: str,
                               detailed: bool,
                               service_type: str) -> typing.Dict[str,
                                                                 typing.Any]:
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
            'services': {
                name: _strip_keys(service, 'host') for name, service
                in service_node['service_results'].items()
                if _service_expected(service, service_type) and
                _host_matches(service, [service_node['private_ip']])
            },
            'metrics': [
                _strip_keys(metric, 'host') for metric in
                service_node['metric_results'].get(service_type, [])
                if _host_matches(metric, [service_node['private_ip']])
            ],
        }
        for service_node in service_nodes.values()
    }

    node_count = len(nodes)

    if service_type == CloudifyNodeType.DB:
        postgresql_name = SERVICE_DESCRIPTIONS['postgresql-9.5']['name']
        if node_count > 1:
            # This is a cluster, remove the postgresql service if present, as
            # patroni will manage it and it will just cause incorrect errors
            for node in nodes.values():
                if postgresql_name in node['services']:
                    node['services'].pop(postgresql_name)

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


def _get_cluster_service_status(nodes: typing.Dict[str, dict],
                                quorum: int) -> str:
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


def _get_overall_state(cluster_status: typing.Dict[str, dict]) -> str:
    found_degraded = False

    for service in cluster_status['services'].values():
        if service['status'] == ServiceStatus.FAIL:
            return ServiceStatus.FAIL
        elif service['status'] == ServiceStatus.DEGRADED:
            found_degraded = True

    return ServiceStatus.DEGRADED if found_degraded else ServiceStatus.HEALTHY


def _get_unit_id(service: typing.Dict) -> str:
    if 'systemd' in service['extra_info']:
        return service['extra_info']['systemd']['unit_id']
    else:
        return service['extra_info']['supervisord']['unit_id']


def _service_expected(service: typing.Dict, service_type: str) -> bool:
    unit_id = _get_unit_id(service)
    if unit_id.endswith('.service'):
        unit_id = unit_id[:-len('.service')]
    return unit_id in SERVICE_ASSIGNMENTS[service_type]


def _host_matches(metric: dict,
                  node_private_ips: typing.Iterable[str]) -> bool:
    if metric and metric.get('host'):
        return metric['host'] in node_private_ips
    return False


def _strip_keys(struct: typing.Dict, keys: typing.Union[list, str]) -> typing.Dict:
    """Return copy of struct but without the keys listed."""
    if not isinstance(keys, list):
        keys = [keys]
    return {k: v for k, v in struct.items() if k not in keys}


def _get_nodes_of_type(cluster_nodes: typing.Dict[str, dict],
                       service_type: str) -> typing.Dict:
    requested_nodes = {}
    for node, details in cluster_nodes.items():
        if service_type in details['services']:
            requested_nodes[node] = details
    return requested_nodes


def _is_external(cluster_nodes: typing.Dict[str, dict],
                 service_type: str) -> bool:
    for node_details in cluster_nodes.values():
        if service_type in node_details['external_services']:
            return True
    return False


def _get_node_state(node: dict):
    if not node['services'] or not node['metrics']:
        # Absence of failure (and everything else) is not success
        return ServiceStatus.FAIL

    for service in node['services'].values():
        if service['status'] != NodeServiceStatus.ACTIVE:
            return ServiceStatus.FAIL

    for metric in node['metrics']:
        if not metric['healthy']:
            return ServiceStatus.FAIL

    return ServiceStatus.HEALTHY


def _parse_prometheus_results(prometheus_results: typing.List[dict]) \
        -> typing.Tuple[typing.Dict[str, dict], typing.Dict[str, list]]:
    service_results: typing.Dict[str, dict] = {}
    metric_results: typing.Dict[str, list] = {}

    def append_service_result(pm: str, res: dict):
        dm = res.get('extra_info', {}).get(pm, {}).get('display_name')
        if not dm:
            return

        if dm not in service_results:
            service_results[dm] = res
            return

        # If any instance is not active, report the service as such
        if service_results[dm].get(
                'status') == NodeServiceStatus.ACTIVE:
            service_results[dm]['status'] = res['status']

        # Update the instances part
        if pm in service_results[dm].get('extra_info', {}):
            # res' process manager is already present in corresponding result
            if 'instances' not in service_results[dm]['extra_info'][pm]:
                service_results[dm]['extra_info'][pm]['instances'] = []
            # keep only one instance per host
            instance_hosts = [
                instance.get('host') for instance
                in service_results[dm]['extra_info'][pm]['instances']
            ]
            for res_instance in res['extra_info'][pm].get('instances'):
                if res_instance.get('host') not in instance_hosts:
                    # ... append an instance to the list of instances
                    service_results[dm]['extra_info'][pm]['instances'].append(
                        res_instance)
        else:
            # if res' process manager is not present in corr. result
            service_results[dm]['extra_info'][pm] = res['extra_info'][pm]

    for result in prometheus_results:
        metric = result.get('metric', {})
        # Technically the second element in the tuple is the metric value, but
        # we only use it to indicate health currently
        timestamp, healthy = result.get('value', [0, ''])
        healthy = bool(int(healthy)) if healthy else False

        process_manager = metric.get('process_manager', '')

        if process_manager:
            service_id = metric.get('name', '')
            service = _get_cloudify_service_description(service_id)

            # Only process services we care about
            if service:
                append_service_result(process_manager, _get_service_status(
                    service_id=service_id,
                    service=service,
                    process_manager=process_manager,
                    is_running=healthy,
                    host=metric.get('host'),
                ))
        else:
            if metric.get('host'):
                processed_data, service_type = _process_metric(
                    metric, timestamp, healthy)
                if service_type not in metric_results:
                    metric_results[service_type] = []
                metric_results[service_type].append(processed_data)
            else:
                # TODO: Log something
                pass
    return service_results, metric_results


def _get_service_status(service_id: str,
                        service: dict,
                        process_manager: str,
                        is_running: bool,
                        host: str) -> typing.Dict[str, typing.Any]:
    return {
        'status': (NodeServiceStatus.ACTIVE if is_running
                   else NodeServiceStatus.INACTIVE),
        'host': host,
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
    metric_name = job

    if job.endswith('postgresql'):
        service_type = CloudifyNodeType.DB
    elif job.endswith('rabbitmq'):
        service_type = CloudifyNodeType.BROKER
    else:
        service_type = CloudifyNodeType.MANAGER
        metric_name = 'http endpoints'

    if timestamp:
        last_check = datetime.fromtimestamp(timestamp).strftime(
            '%Y-%m-%dT%H:%M:%S.%fZ',
        )
    else:
        last_check = 'unknown'

    if metric.get('instance'):
        metric_name += ' ({})'.format(metric.get('instance'))
    if metric.get('host'):
        metric_name += ' on {}'.format(metric.get('host'))

    return {
        'last_check': last_check,
        'healthy': healthy,
        'metric_type': metric.get('__name__', 'unknown'),
        'metric_name': metric_name,
        'host': metric.get('host', 'localhost'),
    }, service_type


def _get_cloudify_service_description(
        metric_name: str) -> typing.Optional[typing.Dict[str, str]]:
    if metric_name in SERVICE_DESCRIPTIONS:
        return SERVICE_DESCRIPTIONS[metric_name]
    elif metric_name.endswith('.service'):
        return _get_cloudify_service_description(metric_name[:-8])
    return None

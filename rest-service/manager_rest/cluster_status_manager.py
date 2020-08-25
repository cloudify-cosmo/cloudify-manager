#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import re
import os
import atexit
import threading
import queue
from collections import namedtuple
from datetime import datetime, timedelta

from flask import current_app

from cloudify.cluster_status import (ServiceStatus,
                                     CloudifyNodeType,
                                     NodeServiceStatus)

from manager_rest.config import instance as config
from manager_rest.prometheus_client import query as prometheus_query
from manager_rest.storage import models, get_storage_manager
from manager_rest.rest.rest_utils import parse_datetime_string

try:
    from cloudify_premium import syncthing_utils
    from cloudify_premium.ha import utils as ha_utils
except ImportError:
    syncthing_utils = None
    ha_utils = None

STATUS = 'status'
SERVICES = 'services'
EXTRA_INFO = 'extra_info'
IS_EXTERNAL = 'is_external'
DB_SERVICE_KEY = 'PostgreSQL'
BROKER_SERVICE_KEY = 'RabbitMQ'
PATRONI_SERVICE_KEY = 'Patroni'
UNINITIALIZED_STATUS = 'Uninitialized'
CLUSTER_STATUS_PATH = '/opt/manager/cluster_statuses'

CloudifyService = namedtuple('CloudifyService', 'name description')
SERVICE_DESCRIPTIONS = {
    'blackbox_exporter': CloudifyService(
        name='Blackbox Exporter',
        description='Prometheus blackbox exporter (HTTP/HTTPS/TCP pings)'),
    'cloudify-amqp-postgres': CloudifyService(
        name='AMQP-Postgres',
        description='Cloudify AMQP PostgreSQL Broker service'),
    'cloudify-composer': CloudifyService(
        name='Cloudify Composer',
        description='Cloudify Composer service'),
    'cloudify-mgmtworker': CloudifyService(
        name='Management Worker',
        description='Cloudify Management Worker service'),
    'cloudify-rabbitmq': CloudifyService(
        name='RabbitMQ Broker',
        description='RabbitMQ Broker service'),
    'cloudify-restservice': CloudifyService(
        name='Manager REST',
        description='Cloudify REST service'),
    'cloudify-stage': CloudifyService(
        name='Cloudify Console',
        description='Cloudify Console service'),
    'cloudify-syncthing': CloudifyService(
        name='Syncthing',
        description='Syncthing service'),
    'etcd': CloudifyService(
        name='Etcd key-value store',
        description='Etcd distributed key-value store service'),
    'haproxy': CloudifyService(
        name='HA Proxy',
        description='HAProxy Load Balancer service'),
    'nginx': CloudifyService(
        name='Webserver',
        description='nginx - high performance web server'),
    'node_exporter': CloudifyService(
        name='Node Exporter',
        description='Prometheus exporter for hardware and OS metrics'),
    'patroni': CloudifyService(
        name='Patroni HA Template',
        description='Patroni HA Template service'),
    'postgresql-9.5': CloudifyService(
        name='PostgreSQL 9.5 database server',
        description='PostgreSQL 9.5 database server'),
    'postgres_exporter': CloudifyService(
        name='Prometheus exporter for PostgreSQL',
        description='Prometheus exporter for PostgreSQL service'),
    'prometheus': CloudifyService(
        name='Prometheus',
        description='Prometheus monitoring service'),
}


class Credentials(object):
    struct = namedtuple('CredentialsStruct', 'username password ca_path')
    data = {}

    @classmethod
    def update(cls, cluster_structure):
        for service_type, service_nodes in cluster_structure.items():
            for service_node in service_nodes:
                if (service_type, service_node.private_ip) in Credentials.data:
                    continue
                ca_path = cls._get_ca_path(service_type) or \
                    cls._store_ca(service_type, service_node)
                Credentials.data[(service_type, service_node.private_ip)] = \
                    Credentials.struct(
                        username=service_node.monitoring_username,
                        password=service_node.monitoring_password,
                        ca_path=ca_path,
                    )

    @classmethod
    def get(cls, service_type, service_node_ip):
        return Credentials.data[(service_type, service_node_ip)]

    @classmethod
    def _get_ca_path(cls, service_type):
        for key, creds in Credentials.data.items():
            if key[0] == service_type and creds.ca_path:
                return creds.ca_path

    @classmethod
    def _store_ca(cls, service_type, service_node):
        if service_type in (CloudifyNodeType.MANAGER, CloudifyNodeType.BROKER):
            ca_path = service_node.write_ca_cert()
            atexit.register(os.unlink, ca_path)
        elif service_type == CloudifyNodeType.DB:
            ca_path = config.postgresql_ca_cert_path
        else:
            ca_path = None
        return ca_path


class ConcurrentStatusChecker(object):
    STOP_THE_WORKER = 'STOP THE WORKER'

    def __init__(self):
        self._in_queue = queue.Queue()
        self._out_queue = queue.Queue()
        self._threads = None

    def _worker(self):
        while True:
            service_node_name, service_node, service_type, status_func = \
                self._in_queue.get()
            if service_type == ConcurrentStatusChecker.STOP_THE_WORKER:
                break
            creds = Credentials.get(service_type, service_node.private_ip)
            try:
                prometheus_response = status_func(
                    'https://{ip}:8009/monitoring/'.format(
                        ip=service_node.private_ip),
                    auth=(creds.username, creds.password),
                    ca_path=creds.ca_path,
                )
            except Exception:
                self._out_queue.put((service_node_name, [],))
            else:
                self._out_queue.put((service_node_name,
                                     prometheus_response,))

    def _initialize_threads(self, number_of_threads):
        self._threads = [
            threading.Thread(target=self._worker)
            for _ in range(number_of_threads)
        ]
        for thread in self._threads:
            thread.daemon = True
            thread.start()

    def get(self, named_service_nodes, service_type, status_func):
        if self._threads is None:
            self._initialize_threads(len(named_service_nodes))
        result = {}
        for service_node_name, service_node in named_service_nodes:
            result[service_node_name] = []
            self._in_queue.put((service_node_name, service_node, service_type,
                                status_func,))
        for _ in range(len(result)):
            try:
                service_node_name, prometheus_response = \
                    self._out_queue.get(
                        timeout=config.monitoring_timeout + 1)
            except queue.Empty:
                pass
            else:
                result[service_node_name] = prometheus_response
        return result


def get_concurrent_status_checker():
    if not hasattr(current_app, 'concurrent_status_checker'):
        current_app.concurrent_status_checker = ConcurrentStatusChecker()
    return current_app.concurrent_status_checker


class ConcurrentServiceChecker(object):
    STOP_THE_WORKER = 'STOP THE WORKER'

    def __init__(self):
        self._in_queue = queue.Queue()
        self._out_queue = queue.Queue()
        self._threads = None

    def _worker(self):
        while True:
            ip_address, service_type = \
                self._in_queue.get()
            if service_type == ConcurrentServiceChecker.STOP_THE_WORKER:
                break
            creds = Credentials.get(service_type, ip_address)
            try:
                prometheus_response = _get_services_status(
                    'https://{ip}:8009/monitoring/'.format(
                        ip=ip_address),
                    auth=(creds.username, creds.password),
                    ca_path=creds.ca_path,
                )
            except Exception:
                self._out_queue.put((ip_address, [],))
            else:
                self._out_queue.put((ip_address,
                                     prometheus_response,))

    def _initialize_threads(self, number_of_threads):
        self._threads = [
            threading.Thread(target=self._worker)
            for _ in range(number_of_threads)
        ]
        for thread in self._threads:
            thread.daemon = True
            thread.start()

    def get(self, node_tuples):
        if self._threads is None:
            self._initialize_threads(len(node_tuples))
        result = {}
        for node_tuple in node_tuples:
            result[node_tuple[0]] = []
            self._in_queue.put(node_tuple)
        for _ in range(len(result)):
            try:
                ip_address, prometheus_response = \
                    self._out_queue.get(
                        timeout=config.monitoring_timeout + 1)
            except queue.Empty:
                pass
            else:
                result[ip_address] = prometheus_response
        return result


def get_concurrent_service_checker():
    if not hasattr(current_app, 'concurrent_service_checker'):
        current_app.concurrent_service_checker = ConcurrentServiceChecker()
    return current_app.concurrent_service_checker


# region Syncthing Status Helpers


def _last_manager_in_cluster():
    storage_manager = get_storage_manager()
    managers = storage_manager.list(models.Manager,
                                    sort={'last_seen': 'desc'})
    active_managers = 0
    for manager in managers:
        # Probably new manager, first status report is yet to arrive
        if manager.status_report_frequency is None:
            active_managers += 1
        else:
            # The manager is considered active, if the time passed since
            # it's last_seen is maximum twice the frequency interval
            # (Nyquist sampling theorem)
            interval = manager.status_report_frequency * 2
            min_last_seen = datetime.utcnow() - timedelta(seconds=interval)

            if parse_datetime_string(manager.last_seen) > min_last_seen:
                active_managers += 1
        if active_managers > 1:
            return False
    return True


def _other_device_was_seen(syncthing_config, device_stats):
    # Add 1 second to the interval for avoiding false negative
    interval = syncthing_config['options']['reconnectionIntervalS'] + 1
    min_last_seen = datetime.utcnow() - timedelta(seconds=interval)

    for device_id, stats in device_stats.items():
        last_seen = parse_datetime_string(stats['lastSeen'])

        # Syncthing is valid when at least one device was seen recently
        if last_seen > min_last_seen:
            return True
    return False


def _is_syncthing_valid(syncthing_config, device_stats):
    if _other_device_was_seen(syncthing_config, device_stats):
        return True

    if _last_manager_in_cluster():
        current_app.logger.debug(
            'It is the last healthy manager in the cluster, no other '
            'devices were seen by File Sync Service'
        )
        return True

    current_app.logger.debug(
        'Inactive File Sync Service - no other devices were seen by it'
    )
    return False


# endregion


def get_syncthing_status():
    try:
        syncthing_config = syncthing_utils.config()
        device_stats = syncthing_utils.device_stats()
    except Exception as err:
        error_message = 'Syncthing check failed with {err_type}: ' \
                        '{err_msg}'.format(err_type=type(err),
                                           err_msg=str(err))
        current_app.logger.error(error_message)
        extra_info = {'connection_check': error_message}
        return NodeServiceStatus.INACTIVE, extra_info

    if _is_syncthing_valid(syncthing_config, device_stats):
        return (NodeServiceStatus.ACTIVE,
                {'connection_check': ServiceStatus.HEALTHY})

    return (NodeServiceStatus.INACTIVE,
            {'connection_check': 'No device was seen recently'})


def _are_keys_in_dict(dictionary, keys):
    return all(key in dictionary for key in keys)


# region Get Cluster Status Helpers


def _generate_cluster_status_structure():
    storage_manager = get_storage_manager()
    return {
        CloudifyNodeType.DB: storage_manager.list(models.DBNodes),
        CloudifyNodeType.MANAGER: storage_manager.list(models.Manager),
        CloudifyNodeType.BROKER:
            storage_manager.list(models.RabbitMQBroker),
    }


def _is_all_in_one(cluster_structure):
    # During the installation of an all-in-one manager, the node_id of the
    # manager node is set to be also the node_id of the db and broker nodes.
    return (cluster_structure[CloudifyNodeType.DB][0].private_ip ==
            cluster_structure[CloudifyNodeType.BROKER][0].private_ip ==
            cluster_structure[CloudifyNodeType.MANAGER][0].private_ip)


# endregion


def get_cluster_status(detailed=False):
    """
    Generate the cluster status using:
    1. The DB tables (managers, rabbitmq_brokers, db_nodes) for the
       structure of the cluster.
    2. The Prometheus monitoring service.
    """
    cluster_services = {}
    cluster_structure = _generate_cluster_status_structure()
    Credentials.update(cluster_structure)
    cloudify_version = cluster_structure[CloudifyNodeType.MANAGER][0].version

    for service_type, service_nodes in cluster_structure.items():
        nodes = _get_nodes_with_status(service_type, service_nodes)
        # It's enough if only one manager is available in a cluster
        quorum = 1 if service_type == 'manager' else -1
        cluster_services[service_type] = {
            STATUS:
                _service_status([n[STATUS] for n in nodes.values()], quorum),
            IS_EXTERNAL:
                service_nodes[0].is_external,
            'nodes':
                # inject `version` key to all nodes
                {node_name: dict(node, version=cloudify_version) for
                 node_name, node in nodes.items()},
        }
    if detailed:
        # report also detailed information on services running on the nodes
        ip_addresses = set((node['private_ip'], cluster_service_type)
                           for cluster_service_type, cluster_service in
                           cluster_services.items()
                           for node in cluster_service['nodes'].values())
        services = _get_service_details(ip_addresses)
        cluster_services = _update_cluster_services(cluster_services, services)

    return {
        STATUS: _simple_status(set([s[STATUS] for s in
                                    cluster_services.values()])),
        SERVICES: cluster_services
    }


def _get_nodes_with_status(service_type, service_nodes):
    status_func = _status_func_for_service(service_type)
    metrics_select_func = _metrics_select_func_for_service(service_type)
    if not status_func or not metrics_select_func:
        return {}
    nodes, remote_node_names = \
        _get_nodes_status_locally(service_nodes, status_func,
                                  metrics_select_func)
    if remote_node_names:
        remote_nodes = _get_nodes_status_remotely(service_nodes, status_func,
                                                  metrics_select_func,
                                                  remote_node_names,
                                                  service_type)
        nodes.update(remote_nodes)
    return nodes


def _get_nodes_status_locally(service_nodes, status_func, metrics_select_func):
    """
    Get nodes' statuses from locally running Prometheus instance.
    :returns dict of nodes' statuses and a list of node names that were not
             found in the locally available metrics.
    """
    prometheus_response = status_func('http://localhost:9090/monitoring/')
    nodes, not_available_nodes = \
        _nodes_from_prometheus_response(prometheus_response,
                                        metrics_select_func, service_nodes)
    return nodes, not_available_nodes.keys()


def _get_nodes_status_remotely(service_nodes, status_func, metrics_select_func,
                               remote_node_names, service_type):
    """
    Get nodes' statuses from remote Prometheus instances.
    :returns dict of nodes' statuses
    """
    def get_service_node(sn_name):
        for sn in service_nodes:
            if sn.name == sn_name:
                return sn

    nodes = {}
    status_getter = get_concurrent_status_checker()
    named_service_nodes = [(name, get_service_node(name))
                           for name in remote_node_names]
    for service_node_name, prometheus_response in status_getter.get(
            named_service_nodes, service_type, status_func).items():
        node, not_available_nodes = _nodes_from_prometheus_response(
            prometheus_response, metrics_select_func, service_nodes)
        # If the remote metrics are not available, assume service_node is down
        # and combine not_available_nodes with those available.
        node.update(not_available_nodes)
        nodes[service_node_name] = node[service_node_name]
    return nodes


def _status_func_for_service(service_type):
    if service_type == CloudifyNodeType.DB:
        return _get_postgresql_status
    if service_type == CloudifyNodeType.BROKER:
        return _get_rabbitmq_status
    if service_type == CloudifyNodeType.MANAGER:
        return _get_manager_status
    return None


def _get_postgresql_status(monitoring_api_uri, auth=None, ca_path=None):
    return prometheus_query(monitoring_api_uri,
                            query_string='up{job=~".*postgresql"} == 1 and ' +
                                         'pg_up{job=~".*postgresql"} == 1',
                            auth=auth,
                            ca_path=ca_path,
                            timeout=config.monitoring_timeout)


def _get_rabbitmq_status(monitoring_api_uri, auth=None, ca_path=None):
    return prometheus_query(monitoring_api_uri,
                            'up{job=~".*rabbitmq"}',
                            auth=auth,
                            ca_path=ca_path,
                            timeout=config.monitoring_timeout)


def _get_manager_status(monitoring_api_uri, auth=None, ca_path=None):
    return prometheus_query(monitoring_api_uri,
                            'probe_success{job=~".*http_.+"}',
                            auth=auth,
                            ca_path=ca_path,
                            timeout=config.monitoring_timeout)


def _get_services_status(monitoring_api_uri, auth=None, ca_path=None):
    return prometheus_query(
        monitoring_api_uri,
        query_string='node_systemd_unit_state{state="active"} or ' +
                     'node_supervisord_up',
        auth=auth,
        ca_path=ca_path,
        timeout=config.monitoring_timeout)


def _metrics_select_func_for_service(service_type):
    if service_type in (CloudifyNodeType.DB,
                        CloudifyNodeType.BROKER,
                        CloudifyNodeType.MANAGER):
        return _metrics_for_host
    return None


def _metrics_for_instance(prometheus_results, ip):
    metrics = []
    for result in prometheus_results:
        instance = result.get('metric', {}).get('instance', '')
        m = re.search(r'(.*://)?(.+):\d+', instance)
        if m:
            instance = m.group(2)
        if _equal_ips(instance, ip):
            metrics.append(result)
    return metrics


def _metrics_for_host(prometheus_results, ip):
    metrics = []
    for result in prometheus_results:
        host = result.get('metric', {}).get('host', '')
        if host and _equal_ips(host, ip):
            metrics.append(result)
        elif not host:
            instance = result.get('metric', {}).get('instance', '')
            m = re.match(r"(.*[^:])(:\d+)", instance)
            if m and _equal_ips(m.group(1), ip):
                metrics.append(result)
            elif instance and not m and _equal_ips(instance, ip):
                metrics.append(result)
    return metrics


def _equal_ips(ip1, ip2):
    if ip1 == ip2:
        return True
    if ip2 == 'localhost':
        return _equal_ips(ip2, ip1)
    if ip1 == 'localhost' and (ip2 == '127.0.0.1' or
                               ip2 == '::1'):
        return True
    return False


def _nodes_from_prometheus_response(prometheus_response,
                                    select_node_metrics_func,
                                    service_nodes):
    nodes = {}
    nodes_not_available = {}
    for service_node in service_nodes.items:
        node_metrics = select_node_metrics_func(prometheus_response,
                                                service_node.private_ip)
        if node_metrics:
            nodes[service_node.name] = {
                STATUS: _simple_status(set(
                    [_status_from_metric(node_metric) for node_metric in
                     node_metrics])),
                'public_ip': service_node.public_ip,
                'private_ip': service_node.private_ip,
            }
        else:
            nodes_not_available[service_node.name] = {
                STATUS: ServiceStatus.FAIL,
                'public_ip': service_node.public_ip,
                'private_ip': service_node.private_ip,
            }
    return nodes, nodes_not_available


def _status_from_metric(metric, healthy_value=1):
    if 'value' in metric and len(metric['value']) == 2:
        if float(metric['value'][1]) == healthy_value:
            return ServiceStatus.HEALTHY
    return ServiceStatus.FAIL


def _simple_status(set_of_statuses):
    if not set_of_statuses or ServiceStatus.FAIL in set_of_statuses:
        return ServiceStatus.FAIL
    if ServiceStatus.DEGRADED in set_of_statuses:
        return ServiceStatus.DEGRADED
    return ServiceStatus.HEALTHY


def _service_status(list_of_statuses, quorum=-1):
    if not list_of_statuses:
        return ServiceStatus.FAIL
    number_of_nodes = len(list_of_statuses)
    healthy = len([s for s in list_of_statuses if s == ServiceStatus.HEALTHY])
    if healthy == number_of_nodes:
        return ServiceStatus.HEALTHY
    if quorum < 0:
        quorum = int(number_of_nodes / 2) + 1
    if healthy >= quorum:
        return ServiceStatus.DEGRADED
    return ServiceStatus.FAIL


def _get_service_details(node_tuples):
    services, nodes_not_available = _get_service_details_locally(node_tuples)
    if nodes_not_available:
        remote_services = _get_service_details_remotely(nodes_not_available)
        services.update(remote_services)
    return services


def _get_service_details_locally(node_tuples):
    prometheus_response = _get_services_status(
        'http://localhost:9090/monitoring/')
    services, services_not_available = _services_from_prometheus_response(
        prometheus_response, _metrics_for_host, node_tuples)
    return services, services_not_available


def _get_service_details_remotely(node_tuples):
    """Get status of the services on not federated nodes."""
    all_services = {}
    service_getter = get_concurrent_service_checker()
    for ip_address, prometheus_reponse in service_getter.get(
            node_tuples).items():
        services, services_not_available = _services_from_prometheus_response(
            prometheus_reponse, _metrics_for_host, node_tuples)
        # If the remote metrics are not available, assume service_node is down
        # and combine not_available_nodes with those available.
        services.update(services_not_available)
        all_services[ip_address] = services[ip_address]
    return all_services


def _services_from_prometheus_response(prometheus_response,
                                       select_node_metrics_func,
                                       node_tuples):
    # node_tuples is a list of two-element tuples: (private_ip, service_type)
    services = {}
    services_not_available = []
    for node_tuple in node_tuples:
        node_metrics = select_node_metrics_func(prometheus_response,
                                                node_tuple[0])
        if node_metrics:
            services[node_tuple[0]] = _service_statuses(node_metrics)
        else:
            services_not_available.append(node_tuple)
    return services, services_not_available


def _service_statuses(node_metrics):
    reported_services = {}
    for node_metric in node_metrics:
        service_id = node_metric.get('metric', {}).get('name')
        service = _get_cloudify_service_description(service_id)
        if not service:
            continue
        process_manager = _get_process_manager(node_metric.get('metric'))
        service_status = _get_service_status(
            service_id, service, process_manager,
            node_metric.get('value')[1] == '1')
        if reported_services.get(service.name, {}).get('extra_info', {}).get(
                process_manager, {}).get('instances'):
            reported_services[service.name]['extra_info'][process_manager][
                'instances'].append(service_status['extra_info'][
                                        process_manager]['instances'])
        else:
            reported_services[service.name] = service_status
    return reported_services


def _get_process_manager(metric):
    if 'systemd' in metric.get('__name__'):
        return 'systemd'
    elif 'supervisord' in metric.get('__name__'):
        return 'supervisord'
    else:
        return 'unknown'


def _get_cloudify_service_description(metric_name):
    if metric_name in SERVICE_DESCRIPTIONS:
        return SERVICE_DESCRIPTIONS[metric_name]
    elif metric_name.endswith('.service'):
        return _get_cloudify_service_description(metric_name[:-8])
    return None


def _get_service_status(service_id, service, process_manager, is_running):
    return {
        'status': (NodeServiceStatus.ACTIVE if is_running
                   else NodeServiceStatus.INACTIVE),
        'extra_info': {
            process_manager: {
                'instances': [
                    {
                        'Description': service.description,
                        'state': ('running' if is_running else 'stopped'),
                        'Id': service_id,
                    },
                ],
                'display_name': service.name,
                'unit_id': service_id,
            },
        },
    }


def _update_cluster_services(cluster_services, services):
    for service_type, cluster_service in cluster_services.items():
        for node_name, node in cluster_service.get('nodes', {}).items():
            node_services = services.get(node['private_ip'], {})
            degraded = False
            if isinstance(node_services, dict):
                for service in node_services.values():
                    if service.get('status') != NodeServiceStatus.ACTIVE:
                        cluster_service['nodes'][
                            node_name]['status'] = ServiceStatus.DEGRADED
                        degraded = True
            else:
                degraded = True
            if degraded:
                if cluster_service['status'] == ServiceStatus.HEALTHY:
                    cluster_service['status'] = ServiceStatus.DEGRADED
            cluster_service['nodes'][node_name].update({
                SERVICES: services.get(node['private_ip'])
            })
    return cluster_services

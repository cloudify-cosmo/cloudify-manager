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

    def __init__(self, number_of_threads=3):
        self._number_of_threads = number_of_threads
        self._in_queue = queue.Queue()
        self._out_queue = queue.Queue()
        self._threads = [
            threading.Thread(target=self._worker)
            for _ in range(self._number_of_threads)
        ]
        self._in_queue_len = 0
        for t in self._threads:
            t.daemon = True
            t.start()

    def _worker(self):
        while True:
            service_type, service_node, service_node_name, status_func = \
                self._in_queue.get()
            if service_type == ConcurrentStatusChecker.STOP_THE_WORKER:
                break
            creds = Credentials.get(service_type, service_node.private_ip)
            prometheus_response = status_func(
                'https://{ip}:53333/monitoring/'.format(
                    ip=service_node.private_ip),
                auth=(creds.username, creds.password),
                ca_path=creds.ca_path
            )
            self._out_queue.put(
                (service_node_name, prometheus_response,)
            )

    def append(self, service_type, service_node, service_node_name,
               status_func):
        self._in_queue.put((service_type, service_node, service_node_name,
                            status_func,))
        self._in_queue_len += 1

    def get_responses(self):
        results = {}
        for _ in range(self._in_queue_len):
            service_node_name, prometheus_response = self._out_queue.get()
            results[service_node_name] = prometheus_response
        return results


def get_concurrent_status_checker():
    if not hasattr(current_app, 'concurrent_status_checker'):
        current_app.concurrent_status_checker = ConcurrentStatusChecker()
    return current_app.concurrent_status_checker


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


def get_cluster_status():
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

    return {
        STATUS: _simple_status(set([s['status'] for s in
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
    for service_node_name in remote_node_names:
        service_node = get_service_node(service_node_name)
        status_getter.append(
            service_type, service_node, service_node_name, status_func
        )
    for service_node_name, prometheus_response in \
            status_getter.get_responses().items():
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
                            query_string='up{job=~".*postgresql"}',
                            auth=auth,
                            ca_path=ca_path)


def _get_rabbitmq_status(monitoring_api_uri, auth=None, ca_path=None):
    return prometheus_query(monitoring_api_uri,
                            'up{job=~".*rabbitmq"}',
                            auth=auth,
                            ca_path=ca_path)


def _get_manager_status(monitoring_api_uri, auth=None, ca_path=None):
    return prometheus_query(monitoring_api_uri,
                            'probe_success{job=~".*http_.+"}',
                            auth=auth,
                            ca_path=ca_path)


def _metrics_select_func_for_service(service_type):
    if service_type in (CloudifyNodeType.DB, CloudifyNodeType.BROKER, ):
        return _metrics_for_instance
    if service_type == CloudifyNodeType.MANAGER:
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
        instance = result.get('metric', {}).get('host', '')
        if _equal_ips(instance, ip):
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

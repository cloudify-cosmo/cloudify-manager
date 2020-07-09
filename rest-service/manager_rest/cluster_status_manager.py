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
from datetime import datetime, timedelta

from flask import current_app

from cloudify.cluster_status import (ServiceStatus,
                                     CloudifyNodeType,
                                     NodeServiceStatus)

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
    cloudify_version = cluster_structure[CloudifyNodeType.MANAGER][0].version

    for service_type, service_nodes in cluster_structure.items():
        nodes = get_nodes_status(service_type, service_nodes)
        cluster_services[service_type] = {
            STATUS: _clustered_status([n[STATUS] for n in nodes.values()]),
            IS_EXTERNAL: service_nodes[0].is_external,
            # inject `version` key to all nodes
            'nodes': {node_name: dict(node, version=cloudify_version) for
                      node_name, node in nodes.items()},
        }

    return {
        STATUS: _decide_on_status(set([s['status'] for s in
                                       cluster_services.values()])),
        SERVICES: cluster_services
    }


def get_nodes_status(service_type, service_nodes):
    status_func = _status_func_for_service(service_type)
    metrics_select_func = _metrics_select_func_for_service(service_type)
    if not status_func or not metrics_select_func:
        return {}
    nodes, remote_node_names = \
        get_status_locally(service_nodes, status_func, metrics_select_func)
    if remote_node_names:
        remote_nodes = get_status_remotely(service_nodes, status_func,
                                           metrics_select_func,
                                           remote_node_names)
        nodes.update(remote_nodes)
    return nodes


def get_status_locally(service_nodes, status_func, metrics_select_func):
    """
    Get nodes' statuses from locally running Prometheus instance.
    :returns A list of node names that were not found in federated results.
    """
    prometheus_response = status_func('http://localhost:9090/monitoring/')

    nodes, not_available_nodes = \
        _nodes_from_prometheus_response(prometheus_response,
                                        metrics_select_func, service_nodes)
    return nodes, not_available_nodes.keys()


def get_status_remotely(service_nodes, status_func, metrics_select_func,
                        remote_node_names):
    """
    Get nodes' statuses from remote Prometheus instances.
    """
    def get_service_node(sn_name):
        for sn in service_nodes:
            if sn.name == sn_name:
                return sn

    nodes = {}
    for service_node_name in remote_node_names:
        service_node = get_service_node(service_node_name)
        prometheus_response = status_func(
            'https://{ip}:53333/monitoring/'.format(
                ip=service_node.private_ip))
        node, not_available_nodes = _nodes_from_prometheus_response(
            prometheus_response, metrics_select_func, service_nodes)
        # As this is our last chance to get a valid status, combine those
        # received from Prometheus with unavailable.
        node.update(not_available_nodes)
        nodes[service_node_name] = node[service_node_name]
    return nodes


def _status_func_for_service(service_type):
    if service_type == 'db':
        return _get_postgresql_status
    if service_type == 'broker':
        return _get_rabbitmq_status
    if service_type == 'manager':
        return _get_manager_status
    return None


def _metrics_select_func_for_service(service_type):
    if service_type in ('db', 'broker', ):
        return _metrics_for_instance_ip
    if service_type == 'manager':
        return _metrics_for_host
    return None

def _get_postgresql_status(monitoring_api_uri):
    # TODO what about ca_cert???
    #  it lives in /etc/cloudify/config.yaml,
    #  is not defined in service_nodes
    # return prometheus_query(
    #     'up{job=~".*postgresql"} and pg_up{job=~".*postgresql"}',
    #     monitoring_api_uri)
    return prometheus_query('up{job=~".*postgresql"}', monitoring_api_uri)


def _get_rabbitmq_status(monitoring_api_uri):
    # TODO remember about about ca_cert???
    #  it lives in /etc/cloudify/config.yaml,
    #  also is defined in service_nodes
    return prometheus_query('up{job=~".*rabbitmq"}', monitoring_api_uri)


def _get_manager_status(monitoring_api_uri):
    # TODO what about ca_cert???
    #  it lives in /etc/cloudify/config.yaml,
    #  is not defined in service_nodes
    return prometheus_query('probe_success{job=~".*http_.+"}',
                            monitoring_api_uri)


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
                STATUS: _decide_on_status(set(
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


def _metrics_for_instance_ip(prometheus_results, ip):
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


def _all_metrics(prometheus_results, _):
    return prometheus_results


def _status_from_metric(metric, healthy_value=1):
    if 'value' in metric and len(metric['value']) == 2:
        if float(metric['value'][1]) == healthy_value:
            return ServiceStatus.HEALTHY
    return ServiceStatus.FAIL


def _clustered_status(list_of_statuses):
    if not list_of_statuses:
        return ServiceStatus.FAIL
    number_of_nodes = len(list_of_statuses)
    healthy = len([s for s in list_of_statuses if s == ServiceStatus.HEALTHY])
    if healthy == number_of_nodes:
        return ServiceStatus.HEALTHY
    quorum = int(number_of_nodes / 2) + 1
    if healthy >= quorum:
        return ServiceStatus.DEGRADED
    return ServiceStatus.FAIL


def _decide_on_status(set_of_statuses):
    if not set_of_statuses or ServiceStatus.FAIL in set_of_statuses:
        return ServiceStatus.FAIL
    if ServiceStatus.DEGRADED in set_of_statuses:
        return ServiceStatus.DEGRADED
    return ServiceStatus.HEALTHY


# OLD STUFF (delete me?) ||


def _get_formatted_nodes(service_nodes, cloudify_version, alerts):
    return {
        node.name: {
            STATUS: _node_status_from_alerts(node, alerts),
            'version': cloudify_version,
            'public_ip': node.public_ip,
            'private_ip': node.private_ip,
            'services': {}
        } for node in service_nodes.items
    }


def _get_service_status(service_type, alerts):
    statuses = set()
    for alert in [a for a in alerts if
                  a.get('labels', {}).get('severity') == 'critical' and
                  a.get('labels', {}).get('instance') is None and
                  _alert_service_type(a) == service_type]:
        statuses.add(_status_from_alert(alert))
    return _decide_on_status(statuses)


def _node_status_from_alerts(node, alerts):
    statuses = set()
    for alert in [a for a in alerts if
                  _alert_node_private_ip(a) == node.private_ip]:
        statuses.add(_status_from_alert(alert))
    return _decide_on_status(statuses)


def _status_from_alert(alert):
    alert_name = alert.get('labels', {}).get('alertname', '')
    if alert_name.endswith('Degraded'):
        return ServiceStatus.DEGRADED
    if alert_name.endswith('Down'):
        return ServiceStatus.FAIL
    return ServiceStatus.HEALTHY


def _alert_service_type(alert):
    job = alert.get('labels', {}).get('job')
    if job.find('postgres') != -1:
        return CloudifyNodeType.DB
    if job.find('rabbit') != -1:
        return CloudifyNodeType.BROKER
    if job.find('http') != -1:
        return CloudifyNodeType.MANAGER
    # One day we may want to use other fields to check of service type, like
    # alert['annotations']['summary'] or alert['labels']['alertname']


def _alert_node_private_ip(alert):
    alert_instance = alert.get('labels', {}).get('instance', '')
    m = re.search(r'(.+):\d+', alert_instance)
    if m:
        alert_instance = m.group(1)
    return alert_instance


# TODO mateumann would that be useful?
def _alert_status(alert):
    state = alert.get('state')
    if state == 'firing':
        return ServiceStatus.FAIL
    if state == 'pending':
        return ServiceStatus.DEGRADED

# region Write Status Report Helpers

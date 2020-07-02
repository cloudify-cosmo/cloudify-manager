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

from manager_rest.storage import models, get_storage_manager
from manager_rest.rest.rest_utils import parse_datetime_string
from manager_rest.prometheus_client import alerts as prometheus_alerts

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


def _get_entire_cluster_status(cluster_services):
    statuses = [service[STATUS] for service in cluster_services.values()]
    if ServiceStatus.FAIL in statuses:
        return ServiceStatus.FAIL
    elif ServiceStatus.DEGRADED in statuses:
        return ServiceStatus.DEGRADED
    return ServiceStatus.HEALTHY


def _is_all_in_one(cluster_structure):
    # During the installation of an all-in-one manager, the node_id of the
    # manager node is set to be also the node_id of the db and broker nodes.
    return (cluster_structure[CloudifyNodeType.DB][0].private_ip ==
            cluster_structure[CloudifyNodeType.BROKER][0].private_ip ==
            cluster_structure[CloudifyNodeType.MANAGER][0].private_ip)


def _get_db_master_replications(db_service):
    for node_name, node in db_service['nodes'].items():
        if not node[SERVICES]:
            continue
        patroni_service = node[SERVICES][PATRONI_SERVICE_KEY]
        patroni_status = patroni_service[EXTRA_INFO]['patroni_status']
        if patroni_status.get('role') == 'master':
            return patroni_status.get('replications_state')
    return None


def _get_db_cluster_status(db_service, expected_nodes_number):
    """
    Get the status of the db cluster. At least one replica should be in
    sync state so the cluster will function. Healthy cluster has all the other
    replicas in streaming state.
    """
    if _should_not_validate_cluster_status(db_service):
        return db_service[STATUS]

    master_replications_state = _get_db_master_replications(db_service)
    if not master_replications_state:
        return ServiceStatus.FAIL

    sync_replica = False
    all_replicas_streaming = True

    for replica in master_replications_state:
        if replica['state'] != 'streaming':
            all_replicas_streaming = False
        elif replica['sync_state'] == 'sync':
            sync_replica = True

    if not sync_replica:
        return ServiceStatus.FAIL

    if (len(master_replications_state) < expected_nodes_number - 1 or
            not all_replicas_streaming):
        return ServiceStatus.DEGRADED

    return db_service[STATUS]


def _should_not_validate_cluster_status(service):
    return service[STATUS] == ServiceStatus.FAIL or service[IS_EXTERNAL]


def _get_broker_cluster_status(broker_service, expected_nodes_number):
    if _should_not_validate_cluster_status(broker_service):
        return broker_service[STATUS]

    broker_nodes = broker_service['nodes']
    active_broker_nodes = {name: node for name, node in broker_nodes.items()
                           if node[STATUS] == ServiceStatus.HEALTHY}

    if expected_nodes_number != len(active_broker_nodes):
        # This should happen only on broker setup
        current_app.logger.error(
            'There are {0} active broker nodes, but there are {1} broker nodes'
            ' registered in the DB.'.format(active_broker_nodes,
                                            expected_nodes_number))
        return ServiceStatus.DEGRADED

    return broker_service[STATUS]


# endregion


def get_cluster_status():
    """
    Generate the cluster status using:
    1. The DB tables (managers, rabbitmq_brokers, db_nodes) for the
       structure of the cluster.
    2. The Prometheus monitoring service.
    """
    alerts = prometheus_alerts()
    cluster_services = {}
    cluster_structure = _generate_cluster_status_structure()
    cloudify_version = cluster_structure[CloudifyNodeType.MANAGER][0].version

    for service_type, service_nodes in cluster_structure.items():
        cluster_services[service_type] = {
            STATUS: _get_service_status(service_type, alerts),
            IS_EXTERNAL: service_nodes[0].is_external,
            'nodes': _get_formatted_nodes(service_nodes, cloudify_version),
        }

    is_all_in_one = _is_all_in_one(cluster_structure)

    if not is_all_in_one:
        db_service = cluster_services[CloudifyNodeType.DB]
        db_service[STATUS] = _get_db_cluster_status(
            db_service, len(cluster_structure[CloudifyNodeType.DB]))
        broker_service = cluster_services[CloudifyNodeType.BROKER]
        broker_service[STATUS] = _get_broker_cluster_status(
            broker_service, len(cluster_structure[CloudifyNodeType.BROKER]))

    return {
        STATUS: _get_entire_cluster_status(cluster_services),
        SERVICES: cluster_services
    }


def _get_service_status(service_type, alerts):
    for alert in [a for a in alerts if
                  a.get('labels', {}).get('severity') == 'critical' and
                  _alert_service_type(a) == service_type]:
        alert_state = alert.get('state')
        if alert_state == 'firing':
            return ServiceStatus.FAIL
        if alert_state == 'pending':
            return ServiceStatus.DEGRADED
    return ServiceStatus.HEALTHY


def _get_formatted_nodes(service_nodes, cloudify_version):
    return {
        node.name: {
            STATUS: ServiceStatus.HEALTHY,
            'version': cloudify_version,
            'public_ip': node.public_ip,
            'private_ip': node.private_ip,
            'services': {}  # TODO fill it with actual data
        } for node in service_nodes.items
    }


def _alert_service_type(alert):
    job = alert.get('labels', {}).get('job')
    if job.find('postgres'):
        return CloudifyNodeType.DB
    if job.find('rabbit'):
        return CloudifyNodeType.BROKER
    if job.find('http'):
        return CloudifyNodeType.MANAGER
    # One day we may want to use other fields to check of service type, like
    # alert['annotations']['summary'] or alert['labels']['alertname']


# TODO mateumann would it be useful?
def _alert_node_private_ip(alert):
    alert_instance = alert.get('labels', {}).get('instance')
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

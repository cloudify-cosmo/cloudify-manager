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

import copy
import json
from os import path, makedirs
from datetime import datetime, timedelta

from flask import current_app

from cloudify.cluster_status import (ServiceStatus,
                                     CloudifyNodeType,
                                     NodeServiceStatus)

from manager_rest import manager_exceptions
from manager_rest.storage import models, get_storage_manager
from manager_rest.rest.rest_utils import parse_datetime_string

STATUS = 'status'
SERVICES = 'services'
EXTRA_INFO = 'extra_info'
IS_EXTERNAL = 'is_external'
DB_SERVICE_KEY = 'PostgreSQL'
BROKER_SERVICE_KEY = 'RabbitMQ'
PATRONI_SERVICE_KEY = 'Patroni'
UNINITIALIZED_STATUS = 'Uninitialized'
CLUSTER_STATUS_PATH = '/opt/manager/cluster_statuses'


def get_report_path(node_type, node_id):
    return '{status_path}/{node_type}_{node_id}.json'.format(
        status_path=CLUSTER_STATUS_PATH, node_type=node_type, node_id=node_id
    )


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


def _generate_service_nodes_status(service_type, service_nodes,
                                   cloudify_version):
    formatted_nodes = {}
    missing_status_reports = {}
    for node in service_nodes:
        node_status = _read_status_report(node,
                                          service_type,
                                          formatted_nodes,
                                          cloudify_version,
                                          missing_status_reports)
        if not node_status:
            continue

        report = node_status['report']
        _generate_node_status(node, formatted_nodes, cloudify_version,
                              report[SERVICES], report[STATUS])
    return formatted_nodes, missing_status_reports


def _read_status_report(node, service_type, formatted_nodes, cloudify_version,
                        missing_status_reports):
    status_file_path = get_report_path(service_type, node.node_id)
    if not path.exists(status_file_path):
        _add_missing_status_reports(node,
                                    formatted_nodes,
                                    service_type,
                                    missing_status_reports,
                                    cloudify_version)
        return None

    try:
        with open(status_file_path, 'r') as status_file:
            node_status = json.load(status_file)

        if _is_report_valid(node_status):
            return node_status
    except ValueError:
        current_app.logger.error(
            'Failed getting the node status from the report {0}, it is not '
            'a valid json file'.format(status_file_path)
        )

    _generate_node_status(node, formatted_nodes, cloudify_version,
                          status=ServiceStatus.FAIL)
    return None


def _generate_node_status(node, formatted_nodes, cloudify_version,
                          node_services=None, status=UNINITIALIZED_STATUS):
    formatted_nodes[node.name] = {
        STATUS: status,
        SERVICES: node_services or {},
        'node_id': node.node_id,
        'version': cloudify_version,
        'public_ip': node.public_ip,
        'private_ip': node.private_ip
    }


def _add_missing_status_reports(node, formatted_nodes, service_type,
                                missing_status_reports, cloudify_version):
    _generate_node_status(node, formatted_nodes, cloudify_version)
    missing_status_reports.setdefault(service_type, [])
    missing_status_reports[service_type].append(node)


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
    return (cluster_structure[CloudifyNodeType.DB][0].node_id ==
            cluster_structure[CloudifyNodeType.BROKER][0].node_id ==
            cluster_structure[CloudifyNodeType.MANAGER][0].node_id)


def _get_service_status(service_nodes):
    service_statuses = {node[STATUS] for name, node in service_nodes.items()}

    # Only one type of status - all the nodes are in Fail/OK/Uninitialized
    if len(service_statuses) == 1:
        return service_statuses.pop()

    # Degraded is when at least one of the nodes is not OK
    return ServiceStatus.DEGRADED


def _is_status_report_updated(report):
    """
    The report is considered updated, if the time passed since the report was
    sent is maximum twice the frequency interval (Nyquist sampling theorem).
    """
    reporting_delta = int(report['reporting_freq']) * 2
    report_time = parse_datetime_string(report['timestamp'])
    return (report_time + timedelta(seconds=reporting_delta) >
            datetime.utcnow())


def _is_report_content_valid(report):
    return (
        _are_keys_in_dict(report, ['reporting_freq', 'report', 'timestamp'])
        and _are_keys_in_dict(report['report'], [STATUS, SERVICES])
        and report['report'][STATUS] in [ServiceStatus.HEALTHY,
                                         ServiceStatus.FAIL]
    )


def _is_report_valid(report):
    return (_is_status_report_updated(report) and
            _is_report_content_valid(report))


def _handle_missing_status_reports(missing_status_reports, cluster_services,
                                   is_all_in_one):
    """Add status data to the nodes with missing status report"""
    if not missing_status_reports:
        return

    manager_service = cluster_services[CloudifyNodeType.MANAGER]
    _handle_missing_manager_report(missing_status_reports, manager_service)

    services_types = [(CloudifyNodeType.DB, DB_SERVICE_KEY),
                      (CloudifyNodeType.BROKER, BROKER_SERVICE_KEY)]
    for service_type, service_key in services_types:
        _handle_missing_non_manager_report(service_type,
                                           service_key,
                                           manager_service['nodes'],
                                           missing_status_reports,
                                           cluster_services,
                                           is_all_in_one)


def _handle_missing_manager_report(missing_status_reports, manager_service):
    """Update the status of manager nodes without status report."""
    missing_managers = missing_status_reports.get(CloudifyNodeType.MANAGER)
    if not missing_managers:
        return

    manager_nodes = manager_service['nodes']
    for manager in missing_managers:
        # A manager's status report should not be missing
        manager_nodes[manager.hostname][STATUS] = ServiceStatus.FAIL
    manager_service[STATUS] = _get_service_status(manager_nodes)


def _handle_missing_non_manager_report(service_type,
                                       service_key,
                                       managers,
                                       missing_status_reports,
                                       cluster_services,
                                       is_all_in_one):
    """Add status data to the nodes with missing status report.

    A node's status report could be missing, due to it being an external
    service (user-provided) or all-in-one manager or it's status reporter
    didn't send a report.
    """
    missing_nodes = missing_status_reports.get(service_type)
    if not missing_nodes:
        return

    service = cluster_services[service_type]
    for missing_node in missing_nodes:
        node_status = ServiceStatus.FAIL

        if missing_node.is_external:
            service_statuses = [
                node[SERVICES].get(service_key, {}).get(STATUS)
                for name, node in managers.items()
            ]
            # The service is healthy if one of the managers is able
            # to connect
            if NodeServiceStatus.ACTIVE in service_statuses:
                node_status = ServiceStatus.HEALTHY

        node_service = {}
        node_name = missing_node.name

        if is_all_in_one:
            # In all-in-one the node name is identical for all nodes
            node_service[service_key] = copy.deepcopy(
                managers[node_name][SERVICES].get(service_key, {})
            )
            if (node_service[service_key].get(STATUS) ==
                    NodeServiceStatus.ACTIVE):
                node_status = ServiceStatus.HEALTHY
        service['nodes'][node_name].update({STATUS: node_status,
                                            SERVICES: node_service})
    service[STATUS] = _get_service_status(service['nodes'])


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

    if (len(master_replications_state) != expected_nodes_number - 1 or
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

    if not _verify_identical_broker_cluster_status(active_broker_nodes):
        return ServiceStatus.FAIL

    if expected_nodes_number != len(active_broker_nodes):
        # This should happen only on broker setup
        current_app.logger.error(
            'There are {0} active broker nodes, but there are {1} broker nodes'
            ' registered in the DB.'.format(active_broker_nodes,
                                            expected_nodes_number))
        return ServiceStatus.DEGRADED

    return broker_service[STATUS]


def _extract_broker_cluster_status(broker_node):
    broker_service = broker_node[SERVICES][BROKER_SERVICE_KEY]
    return broker_service[EXTRA_INFO]['cluster_status']


def _log_different_cluster_status(node_name_a, cluster_status_a,
                                  node_name_b, cluster_status_b):
    current_app.logger.error('{node_name_a} recognizes the cluster: '
                             '{cluster_status_a},\nbut {node_name_b} '
                             'recognizes the cluster {cluster_status_b}.'.
                             format(node_name_a=node_name_a,
                                    cluster_status_a=cluster_status_a,
                                    node_name_b=node_name_b,
                                    cluster_status_b=cluster_status_b))


def _verify_identical_broker_cluster_status(active_nodes):
    are_cluster_statuses_identical = True
    active_nodes_iter = iter(active_nodes.items())
    first_node_name, first_node = next(active_nodes_iter)
    first_node_cluster_status = _extract_broker_cluster_status(first_node)

    for curr_node_name, curr_node in active_nodes_iter:
        curr_node_cluster_status = _extract_broker_cluster_status(curr_node)
        if curr_node_cluster_status != first_node_cluster_status:
            are_cluster_statuses_identical = False
            _log_different_cluster_status(
                first_node_name, first_node_cluster_status,
                curr_node_name, curr_node_cluster_status)

    return are_cluster_statuses_identical


# endregion


def get_cluster_status():
    """
    Generate the cluster status using:
    1. The DB tables (managers, rabbitmq_brokers, db_nodes) for the
       structure of the cluster.
    2. The status reports (saved on the file system) each reporter sends
       with the most updated status of the node.
    """
    cluster_services = {}
    if not path.isdir(CLUSTER_STATUS_PATH):
        return {STATUS: ServiceStatus.DEGRADED, SERVICES: cluster_services}

    cluster_structure = _generate_cluster_status_structure()
    cloudify_version = cluster_structure[CloudifyNodeType.MANAGER][0].version
    missing_status_reports = {}

    for service_type, service_nodes in cluster_structure.items():
        formatted_nodes, missing_reports = _generate_service_nodes_status(
            service_type, service_nodes, cloudify_version
        )
        cluster_services[service_type] = {
            STATUS: _get_service_status(formatted_nodes),
            IS_EXTERNAL: service_nodes[0].is_external,
            'nodes': formatted_nodes
        }
        missing_status_reports.update(missing_reports)

    is_all_in_one = _is_all_in_one(cluster_structure)
    _handle_missing_status_reports(missing_status_reports, cluster_services,
                                   is_all_in_one)
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

# region Write Status Report Helpers


def _verify_status_report_schema(node_id, report):
    if not (_are_keys_in_dict(report['report'], [STATUS, SERVICES])
            and report['report'][STATUS] in [ServiceStatus.HEALTHY,
                                             ServiceStatus.FAIL]):
        raise manager_exceptions.BadParametersError(
            'The status report for {0} is malformed and discarded'.format(
                node_id))


def _verify_report_newer_than_current(node_id, report_time, status_path):
    if not (path.exists(status_path) and path.isfile(status_path)):
        # Nothing to do if the file does not exists
        return
    with open(status_path) as current_report_file:
        current_report = json.load(current_report_file)
    if report_time < parse_datetime_string(current_report['timestamp']):
        current_app.logger.error('The status report for {0} at {1} is before'
                                 ' the latest report'.
                                 format(node_id, report_time))


def _verify_timestamp(node_id, report_time):
    if report_time > datetime.utcnow():
        raise manager_exceptions.BadParametersError(
            'The status report for {0} is in the future at `{1}`'.
            format(node_id, report_time))


def _verify_node_exists(node_id, model):
    if not get_storage_manager().exists(model,
                                        filters={'node_id': node_id}):
        raise manager_exceptions.BadParametersError(
            'The given node id {0} is invalid'.format(node_id))


def _create_statues_folder_if_needed():
    if not path.exists(CLUSTER_STATUS_PATH):
        makedirs(CLUSTER_STATUS_PATH)


def _save_report(report_path, report_dict):
    with open(report_path, 'w') as report_file:
        json.dump(report_dict, report_file)

# endregion


def write_status_report(node_id, model, node_type, report):
    current_app.logger.debug('Received new status report for '
                             '{0} of type {1}...'.format(node_id, node_type))
    _create_statues_folder_if_needed()
    _verify_node_exists(node_id, model)
    _verify_status_report_schema(node_id, report)
    report_time = parse_datetime_string(report['timestamp'])
    _verify_timestamp(node_id, report_time)
    report_path = get_report_path(node_type, node_id)
    _verify_report_newer_than_current(node_id, report_time, report_path)
    _save_report(report_path, report)
    current_app.logger.debug('Successfully updated the status report for '
                             '{0} of type {1}'.format(node_id, node_type))

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


DB_SERVICE_KEY = 'PostgreSQL'
BROKER_SERVICE_KEY = 'RabbitMQ'
UNINITIALIZED_STATUS = 'Uninitialized'
CLUSTER_STATUS_PATH = '/opt/cloudify/cluster_statuses'


def get_report_path(node_type, node_id):
    return '{status_path}/{node_type}_{node_id}.json'.format(
        status_path=CLUSTER_STATUS_PATH, node_type=node_type, node_id=node_id
    )

# region Get Cluster Status Helpers


def _generate_cluster_status_structure():
    storage_manager = get_storage_manager()
    return {
        CloudifyNodeType.DB: storage_manager.list(models.DBNodes),
        CloudifyNodeType.MANAGER: storage_manager.list(models.Manager),
        CloudifyNodeType.BROKER:
            storage_manager.list(models.RabbitMQBroker),
    }


def _generate_service_nodes_status(service_type, service_nodes, cluster_status,
                                   cloudify_version, missing_status_reports):
    formatted_nodes = {}

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
                              report['services'], report['status'])

    cluster_status['services'][service_type] = {
        'status': _get_service_status(formatted_nodes),
        'is_external': service_nodes[0].is_external,
        'nodes': formatted_nodes
    }


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

        if _is_status_report_updated(node_status):
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
        'status': status,
        'node_id': node.node_id,
        'services': node_services or {},
        'version': cloudify_version,
        'public_ip': node.public_ip,
        'private_ip': node.private_ip
    }


def _add_missing_status_reports(node, formatted_nodes, service_type,
                                missing_status_reports, cloudify_version):
    _generate_node_status(node, formatted_nodes, cloudify_version)
    missing_status_reports.setdefault(service_type, [])
    missing_status_reports[service_type].append(node)


def _get_entire_cluster_status(cluster_status):
    statuses = [service['status'] for service in
                cluster_status['services'].values()]
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


def _get_service_status(formatted_nodes):
    service_statuses = {node['status'] for name, node in
                        formatted_nodes.items()}

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


def _handle_missing_status_reports(missing_status_reports, cluster_status,
                                   is_all_in_one):
    """Add status data to the nodes with missing status report"""
    if not missing_status_reports:
        return

    manager_service = cluster_status['services'][CloudifyNodeType.MANAGER]
    _handle_missing_manager_report(missing_status_reports, manager_service)

    services_types = [(CloudifyNodeType.DB, DB_SERVICE_KEY),
                      (CloudifyNodeType.BROKER, BROKER_SERVICE_KEY)]
    for service_type, service_key in services_types:
        _handle_missing_non_manager_report(service_type,
                                           service_key,
                                           manager_service['nodes'],
                                           missing_status_reports,
                                           cluster_status,
                                           is_all_in_one)


def _handle_missing_manager_report(missing_status_reports, manager_service):
    """Update the status of manager nodes without status report."""
    missing_managers = missing_status_reports.get(CloudifyNodeType.MANAGER)
    if not missing_managers:
        return

    manager_nodes = manager_service['nodes']
    for manager in missing_managers:
        # A manager's status report should not be missing
        manager_nodes[manager.hostname]['status'] = ServiceStatus.FAIL
    manager_service['status'] = _get_service_status(manager_nodes)


def _handle_missing_non_manager_report(service_type, service_key, managers,
                                       missing_status_reports, cluster_status,
                                       is_all_in_one):
    """Add status data to the nodes with missing status report.

    A node's status report could be missing, due to it being an external
    service (user-provided) or all-in-one manager or it's status reporter
    didn't send a report.
    """
    missing_nodes = missing_status_reports.get(service_type)
    if not missing_nodes:
        return

    service = cluster_status['services'][service_type]
    for missing_node in missing_nodes:
        node_status = ServiceStatus.FAIL

        if missing_node.is_external:
            service_statuses = [
                manager_node['services'][service_key]['status']
                for manager_node in managers
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
                managers[node_name]['services'].get(service_key, {})
            )
            if (node_service[service_key].get('status') ==
                    NodeServiceStatus.ACTIVE):
                node_status = ServiceStatus.HEALTHY
        service['nodes'][node_name].update({'status': node_status,
                                            'services': node_service})
    service['status'] = _get_service_status(service['nodes'])

# endregion


def get_cluster_status():
    """
    Generate the cluster status using:
    1. The DB tables (managers, rabbitmq_brokers, db_nodes) for the
       structure of the cluster.
    2. The status reports (saved on the file system) each reporter sends
       with the most updated status of the node.
    """
    cluster_status = {'status': ServiceStatus.DEGRADED, 'services': {}}

    if not path.isdir(CLUSTER_STATUS_PATH):
        return cluster_status

    cluster_structure = _generate_cluster_status_structure()
    cloudify_version = cluster_structure[CloudifyNodeType.MANAGER][0].version
    missing_status_reports = {}

    for service_type, service_nodes in cluster_structure.items():
        _generate_service_nodes_status(service_type,
                                       service_nodes,
                                       cluster_status,
                                       cloudify_version,
                                       missing_status_reports)

    _handle_missing_status_reports(missing_status_reports, cluster_status,
                                   _is_all_in_one(cluster_structure))
    cluster_status['status'] = _get_entire_cluster_status(cluster_status)
    return cluster_status


# region Write Status Report Helpers

def _are_keys_in_dict(dictionary, keys):
    return all(key in dictionary for key in keys)


def _verify_status_report_schema(node_id, report):
    if (_are_keys_in_dict(report['report'], ['status', 'services'])
        and report['report']['status'] in [ServiceStatus.HEALTHY,
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
    current_app.logger.info('Received new status report for '
                            '{0} of type {1}...'.format(node_id, node_type))
    _create_statues_folder_if_needed()
    _verify_node_exists(node_id, model)
    _verify_status_report_schema(report)
    report_time = parse_datetime_string(report['timestamp'])
    _verify_timestamp(node_id, report_time)
    report_path = get_report_path(node_type, node_id)
    _verify_report_newer_than_current(node_id, report_time, report_path)
    _save_report(report_path, report)
    current_app.logger.info('Successfully updated the status report for '
                            '{0} of type {1}'.format(node_id, node_type))

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


from flask import request, current_app
from flask_restful_swagger import swagger

from cloudify.cluster_status import CloudifyNodeType, ServiceStatus

from manager_rest.rest import responses
from manager_rest.utils import get_formatted_timestamp
from manager_rest.security.authorization import authorize
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.storage import models, get_storage_manager
from manager_rest.security import SecuredResourceBannedSnapshotRestore
from manager_rest.cluster_status_manager import (STATUS,
                                                 get_cluster_status,
                                                 write_status_report)
from manager_rest.rest.rest_utils import (parse_datetime_string,
                                          verify_and_convert_bool,
                                          get_json_and_verify_params)


class ClusterStatus(SecuredResourceBannedSnapshotRestore):
    @staticmethod
    def _get_request_dict():
        request_dict = get_json_and_verify_params({
            'reporting_freq': {'type': int},
            'report': {'type': dict},
            'timestamp': {'type': basestring}
        })
        return request_dict

    def _write_report(self, node_id, model, node_type):
        report_dict = self._get_request_dict()
        write_status_report(node_id, model, node_type, report_dict)

    @swagger.operation(
        responseClass=responses.Status,
        nickname="cluster-status",
        notes="Returns state of the Cloudify cluster"
    )
    @authorize('cluster_status_get')
    @marshal_with(responses.Status)
    def get(self):
        """Get the status of the entire cloudify cluster"""
        summary_response = verify_and_convert_bool(
            'summary',
            request.args.get('summary', False)
        )
        cluster_status = get_cluster_status()

        # If the response should be only the summary
        if summary_response:
            short_status = cluster_status.get(STATUS)
            status_code = 500 if short_status == ServiceStatus.FAIL else 200
            return {'status': short_status, 'services': {}}, status_code

        return cluster_status


class ManagerClusterStatus(ClusterStatus):
    @authorize('manager_cluster_status_put')
    def put(self, node_id):
        self._update_manager_last_seen(node_id)
        self._write_report(node_id,
                           models.Manager,
                           CloudifyNodeType.MANAGER)

    @staticmethod
    def _update_manager_last_seen(node_id):
        report = request.json.get('report', {})
        if report.get('status') != ServiceStatus.HEALTHY:
            current_app.logger.debug(
                "The manager with node_id: {0} is not healthy, so it's "
                "last_seen is not updated".format(node_id)
            )
            return

        storage_manager = get_storage_manager()
        manager = storage_manager.get(models.Manager, None,
                                      filters={'node_id': node_id})
        manager_time = parse_datetime_string(manager.last_seen)
        report_time = request.json.get('timestamp')
        if report_time and manager_time < parse_datetime_string(report_time):
            manager.last_seen = get_formatted_timestamp()
            manager.status_report_frequency = request.json.get(
                'reporting_freq')
            storage_manager.update(manager)


class DBClusterStatus(ClusterStatus):
    @authorize('db_cluster_status_put')
    def put(self, node_id):
        self._write_report(node_id,
                           models.DBNodes,
                           CloudifyNodeType.DB)


class BrokerClusterStatus(ClusterStatus):
    @authorize('broker_cluster_status_put')
    def put(self, node_id):
        self._write_report(node_id,
                           models.RabbitMQBroker,
                           CloudifyNodeType.BROKER)

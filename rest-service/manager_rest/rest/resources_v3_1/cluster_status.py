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


from flask import request
from flask_restful_swagger import swagger

from cloudify.cluster_status import CloudifyNodeType

from manager_rest.rest import responses
from manager_rest.storage import models
from manager_rest.security.authorization import authorize
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.security import SecuredResourceBannedSnapshotRestore
from manager_rest.cluster_status_manager import (get_cluster_status,
                                                 write_status_report)
from manager_rest.rest.rest_utils import (verify_and_convert_bool,
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

        # If the response should be only the summary - mainly for LB
        if summary_response:
            return {'status': cluster_status['status'], 'services': {}}

        return cluster_status


class ManagerClusterStatus(ClusterStatus):
    @authorize('manager_cluster_status_put')
    def put(self, node_id):
        self._write_report(node_id,
                           models.Manager,
                           CloudifyNodeType.MANAGER)


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

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
#

import os
import json

from flask import request
from flask_restful_swagger import swagger

from manager_rest.rest import responses
from manager_rest.security.authorization import authorize
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.security import SecuredResourceReadonlyMode
from manager_rest.rest.rest_utils import verify_and_convert_bool


STATUS_PATH = '/opt/manager/resources/cluster_status'
MANAGER_PATH = os.path.join(STATUS_PATH, 'manager')
BROKER_PATH = os.path.join(STATUS_PATH, 'broker')
DB_PATH = os.path.join(STATUS_PATH, 'db')


class ClusterStatus(SecuredResourceReadonlyMode):

    @swagger.operation(
        responseClass=responses.Status,
        nickname="cluster-status",
        notes="Returns state of the cloudify cluster"
    )
    @authorize('cluster_status_get')
    @marshal_with(responses.Status)
    def get(self):
        """Get the status of the entire cloudify cluster"""
        summary_response = verify_and_convert_bool(
            'summary',
            request.args.get('summary', False)
        )

        if not os.path.isdir(STATUS_PATH):
            return {'status': 'DEGRADED', 'services': {}}

        cluster_status = {'status': 'OK', 'services': {}}
        self._get_manager_nodes(cluster_status)
        self._get_broker_nodes(cluster_status)
        self._get_db_nodes(cluster_status)

        # If the response should be only the summary - mainly for LB
        if summary_response:
            return {'status': cluster_status['status'], 'services': {}}

        return cluster_status

    def _get_manager_nodes(self, cluster_status):
        self._get_service_nodes(cluster_status, 'manager', MANAGER_PATH)

    def _get_broker_nodes(self, cluster_status):
        if os.path.isdir(BROKER_PATH):
            self._get_service_nodes(cluster_status, 'broker', BROKER_PATH)
        else:
            cluster_status['services']['broker'] = {
                'status': 'OK',
                'is_external': True,
                'nodes': []
            }

    def _get_db_nodes(self, cluster_status):
        if os.path.isdir(DB_PATH):
            self._get_service_nodes(cluster_status, 'db', DB_PATH)
        else:
            cluster_status['services']['db'] = {
                'status': 'OK',
                'is_external': True,
                'nodes': []
            }

    def _get_service_nodes(self, cluster_status, service_name, status_path):
        if not os.path.isdir(status_path):
            return

        one_active_node = False
        service_status = 'OK'
        cluster_status['services'][service_name] = {
            'status': service_status,
            'is_external': False,
            'nodes': []
        }

        for file_name in os.listdir(status_path):
            with open(os.path.join(status_path, file_name), 'r') as f:
                node_status = json.load(f)
            cluster_status['services'][service_name]['nodes'].append({
                'id': file_name[:-5],
                'status': node_status.get('status'),
                'private_ip': node_status.get('private_ip'),
                'public_ip': node_status.get('public_ip'),
                'version': node_status.get('version')
            })

            if node_status.get('status') == 'OK':
                one_active_node = True
            else:
                service_status = 'DEGRADED'

        if service_status == 'DEGRADED':
            if not one_active_node:
                service_status = 'FAIL'
                cluster_status['status'] = 'FAIL'
            elif cluster_status['status'] == 'OK':
                cluster_status['status'] = 'DEGRADED'

        cluster_status['services'][service_name]['status'] = service_status

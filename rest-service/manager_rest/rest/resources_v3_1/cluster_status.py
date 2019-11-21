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
from datetime import datetime

from flask import current_app

from cloudify.cluster_status import CloudifyNodeType

from manager_rest import manager_exceptions
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.security import SecuredResourceReadonlyMode
from manager_rest.rest.rest_utils import (get_json_and_verify_params,
                                          parse_datetime_string)

STATUSES_PATH = '/opt/manager/resources/cluster_status'


class ClusterStatus(SecuredResourceReadonlyMode):
    @staticmethod
    def _get_request_dict():
        request_dict = get_json_and_verify_params({
            'reporting_freq': {'type': int},
            'report': {'type': dict},
            'timestamp': {'type': basestring}
        })
        return request_dict

    @staticmethod
    def _verify_report_newer_than_current(report_time, path):
        if not (os.path.exists(path) and os.path.isfile(path)):
            # Nothing to do if the file does not exists
            return
        with open(path) as current_report_file:
            current_report = json.load(current_report_file)
        if report_time < parse_datetime_string(current_report['timestamp']):
            current_app.logger.error('The new report timestamp `{}` is before'
                                     ' the current report timestamp'.
                                     format(report_time))

    @staticmethod
    def _verify_timestamp(report_time):
        if report_time > datetime.utcnow():
            raise manager_exceptions.BadParametersError(
                'The report timestamp `{0}` is in the future'.
                format(report_time))

    @staticmethod
    def _verify_node_exists(node_id, model):
        if not get_storage_manager().exists(model,
                                            filters={'node_id': node_id}):
            raise manager_exceptions.BadParametersError(
                'The given node id {0} is invalid'.format(node_id))

    @staticmethod
    def _create_statues_folder_if_needed():
        if not os.path.exists(STATUSES_PATH):
            os.makedirs(STATUSES_PATH)

    @staticmethod
    def _save_report(path, report_dict):
        with open(path, 'w') as report_file:
            json.dump(report_dict, report_file)

    def _write_report(self, node_id, model, node_type):
        self._create_statues_folder_if_needed()
        self._verify_node_exists(node_id, model)
        report_dict = self._get_request_dict()
        report_time = parse_datetime_string(report_dict['timestamp'])
        self._verify_timestamp(report_time)
        path = '{status_path}/{node_type}_{node_id}.json'.format(
            status_path=STATUSES_PATH, node_type=node_type, node_id=node_id)
        self._verify_report_newer_than_current(report_time, path)
        self._save_report(path, report_dict)
        current_app.logger.info('Received new status report for '
                                '{0} of type {1}'.format(node_id, node_type))


class ManagerClusterStatus(ClusterStatus):
    @authorize('manager_cluster_status_put')
    def put(self, node_id):
        self._write_report(node_id,
                           models.Manager,
                           CloudifyNodeType.MANAGER)


class DBClusterStatus(ClusterStatus):
    @authorize('db_cluster_status_put')
    def put(self, node_id):
        super(DBClusterStatus, self).put(node_id,
                                         models.DBNodes,
                                         CloudifyNodeType.DB)


class BrokerClusterStatus(ClusterStatus):
    @authorize('broker_cluster_status_put')
    def put(self, node_id):
        super(BrokerClusterStatus, self).put(node_id,
                                             models.RabbitMQBroker,
                                             CloudifyNodeType.BROKER)

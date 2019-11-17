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
from six import string_types

from manager_rest import manager_exceptions
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.security import SecuredResourceReadonlyMode
from manager_rest.rest.rest_utils import (get_json_and_verify_params,
                                          parse_datetime_string)

STATUS_PATH = '/opt/manager/resources/cluster_status'
TIMESTAMP_FORMAT = 'please provide valid date. \nExpected format: ' \
                   'YYYYMMDDHHMM+HHMM or YYYYMMDDHHMM-HHMM i.e: ' \
                   '201801012230-0500 (Jan-01-18 10:30pm EST)'


class ClusterStatus(SecuredResourceReadonlyMode):
    @staticmethod
    def _get_request_dict():
        request_dict = get_json_and_verify_params({
            'reporting_freq': {'type': int},
            'report': {'type': dict},
            'timestamp': {'type': string_types}
        })
        return request_dict

    @staticmethod
    def _node_id_exists(node_id, model):
        ids_list = get_storage_manager().list(model,
                                              filters={'node_id': node_id})
        if len(ids_list) > 0:
            return True
        return False

    @staticmethod
    def _verify_report_newer_than_current(report_time, path):
        with open(path) as current_report_file:
            current_report = json.load(current_report_file)
        if report_time < parse_datetime_string(current_report['timestamp']):
            raise manager_exceptions.BadParametersError(
                'The new report timestamp {0} is before the current report'
                ' timestamp, {1}'.format(report_time, TIMESTAMP_FORMAT))

    @staticmethod
    def _verify_timestamp(report_time):
        if report_time > datetime.utcnow():
            raise manager_exceptions.BadParametersError(
                'The report timestamp `{0}` is in the future, '
                '{1}'.format(report_time, TIMESTAMP_FORMAT))

    @authorize('cluster_status_put')
    def put(self, node_id, model, node_type):
        report_dict = self._get_request_dict()
        if not self._node_id_exists(node_id, model):
            raise manager_exceptions.BadParametersError(
                'The given node id {} is invalid'.format(node_id))
        report_time = parse_datetime_string(report_dict['timestamp'])
        self._verify_timestamp(report_time)
        path = '{status_path}/{node_id}_{node_type}.json'.format(
            status_path=STATUS_PATH, node_id=node_id, node_type=node_type)
        if os.path.exists(path):
            self._verify_report_newer_than_current(report_time, path)
        elif not os.path.exists(STATUS_PATH):
            os.makedirs(STATUS_PATH)
        with open(path, 'w') as report_file:
            json.dump(report_dict, report_file)


class ManagerClusterStatus(ClusterStatus):
    @authorize('manager_cluster_status_put')
    def put(self, node_id, model=models.Manager, node_type='manager'):
        super(ManagerClusterStatus, self).put(node_id, model, node_type)


class DBClusterStatus(ClusterStatus):
    @authorize('db_cluster_status_put')
    def put(self, node_id, model=models.DBNodes, node_type='db'):
        super(DBClusterStatus, self).put(node_id, model, node_type)


class MQClusterStatus(ClusterStatus):
    @authorize('message_queue_cluster_status_put')
    def put(self, node_id, model=models.RabbitMQBroker,
            node_type='message_queue'):
        super(MQClusterStatus, self).put(node_id, model, node_type)

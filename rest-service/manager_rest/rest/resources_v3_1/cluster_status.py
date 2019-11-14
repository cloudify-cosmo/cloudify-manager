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

from manager_rest import manager_exceptions
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.security import SecuredResourceReadonlyMode
from manager_rest.rest.rest_utils import get_json_and_verify_params

STATUS_PATH = '/opt/manager/resources/cluster_status'


class ClusterStatus(SecuredResourceReadonlyMode):
    @staticmethod
    def _get_report():
        request_dict = get_json_and_verify_params({
            'reporting_freq': {'type': int},
            'report': {'type': callable}
        })
        return request_dict

    @authorize('cluster_status_put')
    def put(self, node_uuid, model, node_type):
        report = self._get_report()
        path = '{status_path}/{node_uuid}_{node_type}.json'.format(
            status_path=STATUS_PATH, node_uuid=node_uuid, node_type=node_type)
        uuid_exists = get_storage_manager().exists(model,
                                                   filters={'uuid': node_uuid})
        if not uuid_exists:
            raise manager_exceptions.BadParametersError(
                'The given uuid does not match any node of type '
                '{}'.format(node_type))
        if not os.path.exists(STATUS_PATH):
            os.makedirs(STATUS_PATH)
        with open(path, 'w') as report_file:
            json.dump(report, report_file)


class ManagerClusterStatus(ClusterStatus):
    def put(self, node_uuid, model=models.Manager, node_type='manager'):
        super(ManagerClusterStatus, self).put(node_uuid, model, node_type)


class DbClusterStatus(ClusterStatus):
    def put(self, node_uuid, model=models.DBNodes, node_type='db'):
        super(DbClusterStatus, self).put(node_uuid, model, node_type)


class BrokerClusterStatus(ClusterStatus):
    def put(self, node_uuid, model=models.RabbitMQBroker, node_type='broker'):
        super(BrokerClusterStatus, self).put(node_uuid, model, node_type)

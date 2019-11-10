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

from manager_rest.security.authorization import authorize
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

    @staticmethod
    def _make_dirs(path):
        dirs_path = os.path.dirname(path)
        if not os.path.exists(dirs_path):
            os.makedirs(dirs_path)

    @authorize('cluster_status_put')
    def put(self, instance_type, instance_uuid):
        report = self._get_report()
        path = '{status_path}/{type}/{uuid}.json'.format(
            status_path=STATUS_PATH, type=instance_type, uuid=instance_uuid)
        self._make_dirs(path)
        with open(path, 'w') as report_file:
            json.dump(report, report_file)

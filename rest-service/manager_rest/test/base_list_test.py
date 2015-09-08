#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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
from base_test import BaseServerTestCase


class BaseListTest(BaseServerTestCase):

    def _put_deployment_modification(self, deployment_id='deployment',
                                     modified_nodes={},
                                     node_instances={},
                                     nodes={}):
        resource_path = '/api/{0}/deployment-modifications' \
            .format(self.api_version)
        data = {'deployment_id': deployment_id,
                'modified_nodes': modified_nodes,
                'node_instances': node_instances,
                'nodes': nodes}
        return self.post(resource_path, data).json

    def _mark_deployment_modification_finished(self, modification_id=None):
        resource_path = '/api/{0}/deployment-modifications/{1}/finish' \
            .format(self.api_version, modification_id)
        data = {'modification_id': modification_id}
        return self.post(resource_path, data).json

    def _put_two_test_deployments(self, first_deployment_id='deployment',
                                  sec_deployment_id='deployment2',
                                  first_blueprint_id='blueprint',
                                  sec_blueprint_id='blueprint2'):
        self.put_deployment(deployment_id=first_deployment_id,
                            blueprint_id=first_blueprint_id)
        self.put_deployment(deployment_id=sec_deployment_id,
                            blueprint_id=sec_blueprint_id)
        return first_blueprint_id, first_deployment_id, sec_blueprint_id,\
            sec_deployment_id

    def _put_two_deployment_modifications(self):
        response = self._put_deployment_modification(
            deployment_id=self.first_deployment_id)
        self._mark_deployment_modification_finished(
            modification_id=response['id'])
        self._put_deployment_modification(deployment_id=self.sec_deployment_id)

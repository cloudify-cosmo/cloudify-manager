#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'idanmo'

import uuid

from base_test import BaseServerTestCase
from cloudify_rest_client.exceptions import NoSuchIncludeFieldError


class ModifyTests(BaseServerTestCase):

    def test_modify(self):
        _, _, _, deployment = self.put_deployment(
            deployment_id=str(uuid.uuid4()),
            blueprint_file_name='modify1.yaml')
        modification = self.client.deployments.modify.start(
            deployment.id, nodes={
                'node': {
                    'instances': 200
                }
            })
        self.client.deployments.modify.finish(deployment.id, modification)
        modification = self.client.deployments.modify.start(
            deployment.id, nodes={
                'node': {
                    'instances': 100
                }
            })
        self.client.deployments.modify.finish(deployment.id, modification)
        from pprint import pprint
        pprint(modification)

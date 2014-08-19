########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

__author__ = 'idanmo'

from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_application as deploy
from testenv import undeploy_application as undeploy


class TestContextProperties(TestCase):

    def test_update_runtime_properties(self):
        dsl_path = resource("dsl/set-property.yaml")

        # testing set property
        deployment, _ = deploy(dsl_path)
        node_id = self.client.node_instances.list(
            deployment_id=deployment.id)[0].id
        node_runtime_props = self.client.node_instances.get(
            node_id).runtime_properties
        self.assertEqual('property_value', node_runtime_props['property_name'])

        # testing delete property
        undeploy(deployment.id)
        node_runtime_props = self.client.node_instances.get(
            node_id).runtime_properties
        self.assertNotIn('property_name', node_runtime_props)

    def test_no_update_runtime_properties(self):
        dsl_path = resource("dsl/update-node-state.yaml")
        # simply expecting workflow execution to succeed
        deploy(dsl_path)

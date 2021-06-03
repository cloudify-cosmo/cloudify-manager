########
# Copyright (c) 2013-2019 Cloudify Platform Ltd. All rights reserved
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

import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_deployments


@pytest.mark.usefixtures('cloudmock_plugin')
@pytest.mark.usefixtures('testmockoperations_plugin')
class TestRuntimeProperties(AgentlessTestCase):

    def test_update_runtime_properties(self):
        # testing set property
        node_instance_id, _, dep_id = self._deploy_set_property_application()

        # testing delete property
        self.undeploy_application(dep_id)
        node_runtime_props = self.client.node_instances.get(
            node_instance_id).runtime_properties
        self.assertNotIn('property_name', node_runtime_props)

    def _deploy_set_property_application(self):
        dsl_path = resource("dsl/set_property.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        node_instance_id = self.client.node_instances.list(
            deployment_id=deployment.id)[0].id
        node_runtime_props = self.client.node_instances.get(
            node_instance_id).runtime_properties
        self.assertEqual('property_value', node_runtime_props['property_name'])
        return node_instance_id, node_runtime_props, deployment.id

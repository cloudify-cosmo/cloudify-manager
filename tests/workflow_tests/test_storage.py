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

import uuid

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import create_rest_client
from cloudify_rest_client.exceptions import CloudifyClientError


class TestStorage(TestCase):

    def test_update_node_bad_version(self):
        deploy(resource("dsl/basic.yaml"))
        client = create_rest_client()
        instance = client.node_instances.list()[0]
        instance = client.node_instances.get(instance.id)  # need the version

        props = {'key': 'value'}
        result = client.node_instances.update(instance.id,
                                              state='started',
                                              runtime_properties=props,
                                              version=instance.version,)
        self.assertEquals(instance.version+1, result.version)
        self.assertEquals(instance.id, result.id)
        self.assertDictContainsSubset(props, result.runtime_properties)
        self.assertEquals('started', result.state)

        # making another call with a bad version
        self.assertRaises(
            CloudifyClientError, client.node_instances.update,
            instance.id, version=1)

    def test_deployment_inputs(self):
        blueprint_id = str(uuid.uuid4())
        blueprint = self.client.blueprints.upload(resource("dsl/basic.yaml"),
                                                  blueprint_id)
        inputs = blueprint.plan['inputs']
        self.assertEqual(1, len(inputs))
        self.assertTrue('install_agent' in inputs)
        self.assertFalse(inputs['install_agent']['default'])
        self.assertTrue(
            len(inputs['install_agent']['description']) > 0)
        deployment_id = str(uuid.uuid4())
        deployment = self.client.deployments.create(blueprint.id,
                                                    deployment_id)
        self.assertEqual(1, len(deployment.inputs))
        self.assertTrue('install_agent' in deployment.inputs)
        self.assertFalse(deployment.inputs['install_agent'])

    def test_node_operation_different_inputs(self):
        """
        Tests storing different nodes with different structured inputs for
        the same operation.
        """
        blueprint_id = str(uuid.uuid4())
        blueprint = self.client.blueprints.upload(
            resource("dsl/two_nodes_different_inputs.yaml"),
            blueprint_id)
        deployment_id = str(uuid.uuid4())
        self.client.deployments.create(blueprint.id, deployment_id)

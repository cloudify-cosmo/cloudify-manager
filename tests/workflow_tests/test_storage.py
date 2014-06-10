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

__author__ = 'ran'


from workflow_tests.testenv import get_resource as resource
from workflow_tests.testenv import deploy_application as deploy
from workflow_tests.testenv import TestCase
from workflow_tests.testenv import create_new_rest_client
from cloudify_rest_client.exceptions import CloudifyClientError


class TestStorage(TestCase):

    def test_update_node_bad_version(self):
        deploy(resource("dsl/basic.yaml"))
        client = create_new_rest_client()
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

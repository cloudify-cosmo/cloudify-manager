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

import uuid

from testenv import TestCase
from testenv import create_new_rest_client
from cloudify_rest_client.exceptions import CloudifyClientError


class TestStorage(TestCase):

    def test_update_node_bad_version(self):
        client = create_new_rest_client()

        instance_id = str(uuid.uuid4())
        deployment_id = str(uuid.uuid4())
        version = 1
        result = client.node_instances.create(instance_id, deployment_id, {})
        self.assertEquals(version, result.version)
        self.assertEquals(instance_id, result.id)
        self.assertEquals({}, result.runtime_properties)

        props = {'key': 'value'}
        result = client.node_instances.update(instance_id,
                                              state='started',
                                              runtime_properties=props,
                                              version=result.version,)
        self.assertEquals(2, result.version)
        self.assertEquals(instance_id, result.id)
        self.assertEquals(props, result.runtime_properties)
        self.assertEquals('started', result.state)

        # making another call with a bad version
        self.assertRaises(
            CloudifyClientError, client.node_instances.update,
            instance_id, version=1)

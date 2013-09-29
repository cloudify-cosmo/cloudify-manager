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

import unittest
import tasks as t
import json


class TestDSLParser(unittest.TestCase):

    def test_tier_processing(self):
        result = t.create_node_instances(nodes_json)
        parsed = json.loads(result)
        extra = parsed["nodes_extra"]
        self.assertFalse("simple_web_server.host" in extra)
        self.assertTrue("simple_web_server.tier" in extra)
        self.assertTrue("simple_web_server.host_1" in extra)
        self.assertTrue("simple_web_server.host_2" in extra)
        self.assertEquals(3, len(extra))
        nodes_list = parsed["nodes"]
        nodes = {x.id: x for x in nodes_list}
        self.assertFalse("simple_web_server.host" in nodes)
        self.assertTrue("simple_web_server.tier" in nodes)
        self.assertTrue("simple_web_server.host_1" in nodes)
        self.assertTrue("simple_web_server.host_2" in nodes)
        self.assertEquals(3, len(nodes))


nodes_json = """
{
    "nodes_extra": {
        "simple_web_server.tier": {
            "super_types": [
                "cloudify.tosca.types.tier",
                "node"
            ],
            "relationships": []
        },
        "simple_web_server.host": {
            "super_types": [
                "cloudify.tosca.types.host",
                "node"
            ],
            "relationships": []
        }
    },
    "nodes": [
        {
            "id": "simple_web_server.host",
            "properties": {
                "install_agent": "false",
                "cloudify_runtime": {}
            },
            "relationships": [],
            "host_id": "simple_web_server.host"
        },
        {
            "id": "simple_web_server.tier",
            "properties": {
                "nodes": [
                    "host"
                ],
                "number_of_instances": 2
            },
            "relationships": []
        }
    ]
}
"""
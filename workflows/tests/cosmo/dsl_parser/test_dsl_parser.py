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

import tasks
from testenv import get_resource_as_string


class TestDSLParser(unittest.TestCase):

    def test_get_tier_simple_name(self):

        full_name = 'application.tier'
        self.assertEqual('tier', tasks.get_tier_simple_name(full_name))

    def test_create_node_instances(self):

        node = {
            "id": "simple_web_server.host",
            "properties": {
                "install_agent": "false",
                "cloudify_runtime": {}
            },
            "relationships": [],
            "host_id": "simple_web_server.host"
        }

        expected_instances = [
            {
                "id": "simple_web_server.web_tier.host_1",
                "properties": {
                    "install_agent": "false",
                    "cloudify_runtime": {}
                },
                "relationships": [],
                "host_id": "simple_web_server.host"
            },
            {
                "id": "simple_web_server.web_tier.host_2",
                "properties": {
                    "install_agent": "false",
                    "cloudify_runtime": {}
                },
                "relationships": [],
                "host_id": "simple_web_server.host"
            }
        ]

        instances = tasks.create_node_instances(node, 2, 'test.web_tier')
        self.assertEqual(instances, expected_instances)

    def test_prepare_multi_instance_plan(self):

        plan = get_resource_as_string('dsl_parser/multi_instance.json')

        # everything in the new plan stays the same except for nodes that belonged to a tier.
        expected_plan = {
            "nodes_extra": {
                "simple_web_server.web_tier": {
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
                },
                "simple_web_server.non_tier_host": {
                    "super_types": [
                        "cloudify.tosca.types.host",
                        "node"
                    ],
                    "relationships": []
                }
            },
            "nodes": [
                {
                    "id": "simple_web_server.web_tier.host_1",
                    "properties": {
                        "install_agent": "false",
                        "cloudify_runtime": {}
                    },
                    "relationships": [],
                    "host_id": "simple_web_server.host"
                },
                {
                    "id": "simple_web_server.web_tier.host_2",
                    "properties": {
                        "install_agent": "false",
                        "cloudify_runtime": {}
                    },
                    "relationships": [],
                    "host_id": "simple_web_server.host"

                },
                {
                    "id": "simple_web_server.non_tier_host",
                    "properties": {
                        "install_agent": "false",
                        "cloudify_runtime": {}
                    },
                    "relationships": [],
                    "host_id": "simple_web_server.host"
                },
                {
                    "id": "simple_web_server.web_tier",
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

        new_plan = tasks.prepare_multi_instance_plan(plan)
        self.assertEqual(new_plan, expected_plan)

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
                "id": "simple_web_server.host_1",
                "properties": {
                    "install_agent": "false",
                    "cloudify_runtime": {}
                },
                "relationships": [],
                "host_id": "simple_web_server.host_1"
            },
            {
                "id": "simple_web_server.host_2",
                "properties": {
                    "install_agent": "false",
                    "cloudify_runtime": {}
                },
                "relationships": [],
                "host_id": "simple_web_server.host_2"
            }
        ]

        instances = tasks.create_node_instances(node, 2)
        self.assertEqual(instances, expected_instances)

    def test_prepare_multi_instance_plan(self):

        plan = get_resource_as_string('dsl_parser/multi_instance.json')

        # everything in the new plan stays the same except for nodes that belonged to a tier.
        expected_plan = {
            "nodes_extra": {
                "multi_instance.host": {
                    "super_types": [
                        "cloudify.tosca.types.host",
                        "node"
                    ]
                },
                "multi_instance.db": {
                    "super_types": [
                        "cloudify.tosca.types.db_server",
                        "cloudify.tosca.types.middleware_server",
                        "node"
                    ],
                    "relationships": [
                        "multi_instance.host"
                    ]
                }
            },
            "nodes": [
                {
                    "id": "multi_instance.db_1",
                    "plugins": {
                        "app_installer": {
                            "name": "app_installer",
                            "interface": "cloudify.tosca.interfaces.app_module_installer",
                            "agent_plugin": "true",
                            "url": "app_installer_mock.zip"
                        },
                        "dbmock": {
                            "name": "dbmock",
                            "interface": "cloudify.tosca.interfaces.middleware_component_installer",
                            "agent_plugin": "true",
                            "url": "dbmock.zip"
                        }
                    },
                    "host_id": "multi_instance.host_1"
                },
                {
                    "id": "multi_instance.db_2",
                    "plugins": {
                        "app_installer": {
                            "name": "app_installer",
                            "interface": "cloudify.tosca.interfaces.app_module_installer",
                            "agent_plugin": "true",
                            "url": "app_installer_mock.zip"
                        },
                        "dbmock": {
                            "name": "dbmock",
                            "interface": "cloudify.tosca.interfaces.middleware_component_installer",
                            "agent_plugin": "true",
                            "url": "dbmock.zip"
                        }
                    },
                    "host_id": "multi_instance.host_2"
                },
                {
                    "id": "multi_instance.host_1",
                    "plugins": {
                        "cloudify.tosca.artifacts.plugin.worker_installer": {
                            "name": "cloudify.tosca.artifacts.plugin.worker_installer",
                            "interface": "cloudify.tosca.interfaces.worker_installer",
                            "agent_plugin": "false",
                            "url": "cloudify/poc/artifacts/plugins/celery-worker-installer.zip"
                        },
                        "cloudmock": {
                            "name": "cloudmock",
                            "interface": "cloudify.tosca.interfaces.host_provisioner",
                            "agent_plugin": "false",
                            "url": "cloudmock.zip"
                        },
                        "cloudify.tosca.artifacts.plugin.plugin_installer": {
                            "name": "cloudify.tosca.artifacts.plugin.plugin_installer",
                            "interface": "cloudify.tosca.interfaces.plugin_installer",
                            "agent_plugin": "true",
                            "url": "cloudify/poc/artifacts/plugins/celery-worker-plugin-installer.zip"
                        }
                    }
                },
                {
                    "id": "multi_instance.host_2",
                    "plugins": {
                        "cloudify.tosca.artifacts.plugin.worker_installer": {
                            "name": "cloudify.tosca.artifacts.plugin.worker_installer",
                            "interface": "cloudify.tosca.interfaces.worker_installer",
                            "agent_plugin": "false",
                            "url": "cloudify/poc/artifacts/plugins/celery-worker-installer.zip"
                        },
                        "cloudmock": {
                            "name": "cloudmock",
                            "interface": "cloudify.tosca.interfaces.host_provisioner",
                            "agent_plugin": "false",
                            "url": "cloudmock.zip"
                        },
                        "cloudify.tosca.artifacts.plugin.plugin_installer": {
                            "name": "cloudify.tosca.artifacts.plugin.plugin_installer",
                            "interface": "cloudify.tosca.interfaces.plugin_installer",
                            "agent_plugin": "true",
                            "url": "cloudify/poc/artifacts/plugins/celery-worker-plugin-installer.zip"
                        }
                    }
                }
            ]
        }

        new_plan = tasks.prepare_multi_instance_plan(plan)
        self.assertEqual(new_plan, expected_plan)

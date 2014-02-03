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

from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_application as deploy
from testenv import get_deployment_workflows


class TestDeploymentWorkflows(TestCase):

    def test_deployment_workflows(self):
        dsl_path = resource("dsl/basic.yaml")
        deployment = deploy(dsl_path)
        deployment_id = deployment.id
        blueprint_id = deployment.blueprintId
        workflows = get_deployment_workflows(deployment_id)
        self.assertEqual(blueprint_id, workflows.blueprintId)
        self.assertEqual(deployment_id, workflows.deploymentId)
        self.assertEqual(3, len(workflows.workflows))
        self.assertEqual('mock_workflow', workflows.workflows[0].name)
        self.assertEqual('install', workflows.workflows[1].name)
        self.assertEqual('uninstall', workflows.workflows[2].name)

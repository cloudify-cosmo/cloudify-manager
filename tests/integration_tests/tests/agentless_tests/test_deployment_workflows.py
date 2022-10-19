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

import pytest

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource
from integration_tests.tests.utils import (
    verify_deployment_env_created,
    wait_for_blueprint_upload,
    wait_for_deployment_deletion_to_complete
)
from integration_tests.tests.utils import do_retries

pytestmark = pytest.mark.group_workflows


@pytest.mark.usefixtures('testmockoperations_plugin')
@pytest.mark.usefixtures('cloudmock_plugin')
@pytest.mark.usefixtures('mock_workflows_plugin')
class TestDeploymentWorkflows(AgentlessTestCase):

    def test_deployment_workflows(self):
        dsl_path = resource("dsl/custom_workflow_mapping.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        deployment_id = deployment.id
        workflows = self.client.deployments.get(deployment_id).workflows
        self.assertEqual(15, len(workflows))
        wf_ids = [x.name for x in workflows]
        self.assertIn('uninstall', wf_ids)
        self.assertIn('install', wf_ids)
        self.assertIn('execute_operation', wf_ids)
        self.assertIn('custom', wf_ids)
        self.assertIn('scale', wf_ids)
        self.assertIn('heal', wf_ids)
        self.assertIn('install_new_agents', wf_ids)
        self.assertIn('start', wf_ids)
        self.assertIn('stop', wf_ids)
        self.assertIn('restart', wf_ids)
        self.assertIn('check_status', wf_ids)
        self.assertIn('check_drift', wf_ids)

    def test_workflow_parameters_pass_from_blueprint(self):
        dsl_path = resource('dsl/workflow_parameters.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)
        do_retries(verify_deployment_env_created,
                   timeout_seconds=30,
                   container_id=self.env.container_id,
                   client=self.client,
                   deployment_id=deployment_id)
        execution = self.client.executions.start(deployment_id,
                                                 'custom_execute_operation')
        self.wait_for_execution_to_end(execution)

        node_id = self.client.node_instances.list(
            deployment_id=deployment_id)[0].id
        node_instance = self.client.node_instances.get(node_id)
        invocations = node_instance.runtime_properties[
            'mock_operation_invocation'
        ]
        self.assertEqual(1, len(invocations))
        self.assertDictEqual(invocations[0], {'test_key': 'test_value'})

    def test_get_workflow_parameters(self):
        dsl_path = resource('dsl/workflow_parameters.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)

        workflows = self.client.deployments.get(deployment_id).workflows
        execute_op_workflow = next(wf for wf in workflows if
                                   wf.name == 'another_execute_operation')
        expected_params = {
            u'node_id': {u'default': u'test_node'},
            u'operation': {},
            u'properties': {
                u'default': {
                    u'key': u'test_key',
                    u'value': u'test_value'
                }
            }
        }
        self.assertEqual(expected_params, execute_op_workflow.parameters)

    def test_delete_botched_deployment(self):
        dsl_path = resource('dsl/basic.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)

        self.client.blueprints.upload(dsl_path, blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)
        execution = self.client.executions.list(deployment_id=deployment_id)[0]
        self.wait_for_execution_to_end(execution)

        self.client.deployments.delete(deployment_id)
        wait_for_deployment_deletion_to_complete(deployment_id, self.client)
        try:
            self.client.deployments.get(deployment_id)
            self.fail("Expected deployment to be deleted")
        except CloudifyClientError as e:
            self.assertEqual(404, e.status_code)

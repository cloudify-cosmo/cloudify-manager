#########
# Copyright (c) 2020 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.


# from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test import base_test
from manager_rest.test.attribute import attr


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class WorkflowsTestCase(base_test.BaseServerTestCase):

    def test_workflows_list_default_workflows(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_deployment(
            deployment_id='test1',
            blueprint_file_name='blueprint.yaml',
        )
        workflows = self.client.workflows.list(deployment_id='test1')

        assert set(w.name for w in workflows.items) == {
            'install', 'update', 'uninstall', 'start', 'stop', 'restart',
            'execute_operation', 'heal', 'scale', 'install_new_agents',
            'validate_agents', 'rollback', 'pull'}

    def test_workflows_list_with_additional_workflow(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_deployment(
            deployment_id='test1',
            blueprint_file_name='blueprint_with_workflows.yaml',
        )
        workflows = self.client.workflows.list(deployment_id='test1')
        assert 'mock_workflow' in (w.get('name') for w in workflows.items)

    def test_workflows_list_workflow_with_params(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_deployment(
            deployment_id='test1',
            blueprint_file_name='blueprint_with_workflows_with_parameters_'
                                'types.yaml',
        )
        workflows = self.client.workflows.list(deployment_id='test1')

        mock_workflows = [w for w in workflows if w.name == 'mock_workflow']
        assert len(mock_workflows) == 1
        mock_workflow = mock_workflows[0]
        assert mock_workflow.operation == 'workflows.default.install'
        assert len(mock_workflow.parameters) == 20

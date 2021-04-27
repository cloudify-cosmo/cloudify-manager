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

from manager_rest.constants import LabelsOperator
from manager_rest.rest.filters_utils import FilterRule
from manager_rest.test import base_test
from manager_rest.test.attribute import attr


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class WorkflowsTestCase(base_test.BaseServerTestCase):

    def setUp(self):
        super().setUp()
        self.put_deployment(
            deployment_id='d1',
            blueprint_id='b1',
            blueprint_file_name='blueprint.yaml',
            labels=[{'zxc': '1'}, {'asd': '1'}]
        )
        self.put_deployment(
            deployment_id='d2',
            blueprint_id='b2',
            blueprint_file_name='blueprint_with_workflows.yaml',
            labels=[{'zxc': '1'}, {'asd': '2'}]
        )
        self.put_deployment(
            deployment_id='d3',
            blueprint_id='b3',
            blueprint_file_name='blueprint_with_workflows_with_parameters_'
                                'types.yaml',
            labels=[{'zxc': '2'}, {'asd': '2'}]
        )

    def test_workflows_list_default_workflows(self):
        workflows = self.client.workflows.list(id='d1')
        assert set(w.name for w in workflows.items) == {
            'install', 'update', 'uninstall', 'start', 'stop', 'restart',
            'execute_operation', 'heal', 'scale', 'install_new_agents',
            'validate_agents', 'rollback', 'pull'}

    def test_workflows_list_with_additional_workflow(self):
        workflows = self.client.workflows.list(id='d2')
        assert 'mock_workflow' in (w.get('name') for w in workflows.items)

    def test_workflows_list_workflow_with_params(self):
        workflows = self.client.workflows.list(id='d3')
        mock_workflows = [w for w in workflows if w.name == 'mock_workflow']
        assert len(mock_workflows) == 1
        assert len(mock_workflows[0].parameters.keys()) > 0

    def test_workflows_list_nonexistent(self):
        workflows = self.client.workflows.list(id='nonexistent')
        assert workflows.items == []

    def test_workflows_list_group(self):
        self.client.deployment_groups.put('g1', deployment_ids=['d2', 'd3'])
        workflows_for_g1 = self.client.workflows.list(deployment_group_id='g1')
        assert workflows_for_g1
        workflows_for_d2 = self.client.workflows.list(id='d2')
        assert len(workflows_for_g1.items) == len(workflows_for_d2.items)

    def test_workflows_by_filter_rule(self):
        workflows_by_filter = self.client.workflows.list(
            filter_rules=[FilterRule('zxc', ['1'], LabelsOperator.NOT_ANY_OF,
                                     'label')])
        workflows_for_d3 = self.client.workflows.list(id='d3')
        assert workflows_by_filter.items == workflows_for_d3.items

    def test_workflows_by_filter_id(self):
        self.create_filter(
            self.client.deployments_filters, 'f1',
            [FilterRule('zxc', ['1'], LabelsOperator.ANY_OF, 'label'),
             FilterRule('asd', ['1'], LabelsOperator.ANY_OF, 'label')])
        self.create_filter(
            self.client.deployments_filters, 'f2',
            [FilterRule('asd', ['3'], LabelsOperator.NOT_ANY_OF, 'label')])
        workflows_for_f1 = self.client.workflows.list(filter_id='f1')
        assert len(workflows_for_f1) == 13
        workflows_for_f2 = self.client.workflows.list(filter_id='f2')
        assert len(workflows_for_f2) == 14
        assert (set(w.name for w in workflows_for_f2) -
                set(w.name for w in workflows_for_f1)) == {'mock_workflow'}

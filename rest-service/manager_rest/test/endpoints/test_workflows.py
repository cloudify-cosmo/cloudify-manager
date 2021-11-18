from manager_rest.constants import LabelsOperator
from manager_rest.rest.filters_utils import FilterRule
from manager_rest.test import base_test


class WorkflowsTestCase(base_test.BaseServerTestCase):

    def _put_deployments(self, deployment_ids):
        if 'd1' in deployment_ids:
            self.put_deployment(
                deployment_id='d1',
                blueprint_id='b1',
                blueprint_file_name='blueprint.yaml',
                labels=[{'zxc': '1'}, {'asd': '1'}]
            )
        if 'd2' in deployment_ids:
            self.put_deployment(
                deployment_id='d2',
                blueprint_id='b2',
                blueprint_file_name='blueprint_with_workflows.yaml',
                labels=[{'zxc': '1'}, {'asd': '2'}]
            )
        if 'd3' in deployment_ids:
            self.put_deployment(
                deployment_id='d3',
                blueprint_id='b3',
                blueprint_file_name='blueprint_with_workflows_with_parameters_'
                                    'types.yaml',
                labels=[{'zxc': '2'}, {'asd': '2'}]
            )

    def test_workflows_list_with_additional_workflow(self):
        self._put_deployments(['d2'])
        workflows = self.client.workflows.list(id='d2')
        assert 'mock_workflow' in (w.name for w in workflows.items)

    def test_workflows_list_workflow_with_params(self):
        self._put_deployments(['d3'])
        workflows = self.client.workflows.list(id='d3')
        mock_workflows = [w for w in workflows if w.name == 'mock_workflow']
        assert len(mock_workflows) == 1
        assert len(mock_workflows[0].parameters.keys()) > 0

    def test_workflows_list_nonexistent(self):
        self._put_deployments(['d1'])
        workflows = self.client.workflows.list(id='nonexistent')
        assert workflows.items == []

    def test_workflows_list_group(self):
        self._put_deployments(['d2', 'd3'])
        self.client.deployment_groups.put('g1', deployment_ids=['d2', 'd3'])
        workflows_for_g1 = self.client.workflows.list(deployment_group_id='g1')
        assert workflows_for_g1
        workflows_for_d2 = self.client.workflows.list(id='d2')
        assert len(workflows_for_g1.items) == len(workflows_for_d2.items)

    def test_workflows_by_filter_rule(self):
        self._put_deployments(['d1', 'd2', 'd3'])
        workflows_by_filter = self.client.workflows.list(
            filter_rules=[FilterRule('zxc', ['1'], LabelsOperator.NOT_ANY_OF,
                                     'label')])
        workflows_for_d3 = self.client.workflows.list(id='d3')
        assert workflows_by_filter.items == workflows_for_d3.items

    def test_workflows_by_filter_id(self):
        self._put_deployments(['d1', 'd2', 'd3'])
        self.create_filter(
            self.client.deployments_filters, 'f1',
            [FilterRule('zxc', ['1'], LabelsOperator.ANY_OF, 'label'),
             FilterRule('asd', ['1'], LabelsOperator.ANY_OF, 'label')])
        self.create_filter(
            self.client.deployments_filters, 'f2',
            [FilterRule('asd', ['3'], LabelsOperator.NOT_ANY_OF, 'label')])
        workflows_for_f1 = self.client.workflows.list(filter_id='f1')
        workflows_for_f2 = self.client.workflows.list(filter_id='f2')
        assert workflows_for_f1
        assert (set(w.name for w in workflows_for_f2) -
                set(w.name for w in workflows_for_f1)) == {'mock_workflow'}

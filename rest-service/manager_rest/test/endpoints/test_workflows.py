import itertools

from manager_rest.constants import LabelsOperator
from manager_rest.storage import models
from manager_rest.rest.filters_utils import FilterRule
from manager_rest.test import base_test


class WorkflowsTestCase(base_test.BaseServerTestCase):
    def _label(self, deployment, key, value):
        deployment.labels.append(models.DeploymentLabel(
            key=key,
            value=value,
            creator=deployment.creator,
        ))

    def _deployment(self, dep_id, **kwargs):
        labels = kwargs.pop('labels', [])
        bp = models.Blueprint(
            id=dep_id + '_bp',
            creator=self.user,
            tenant=self.tenant,
        )
        dep = models.Deployment(
            id=dep_id,
            blueprint=bp,
            creator=self.user,
            tenant=self.tenant,
            **kwargs
        )
        for key, value in labels:
            self._label(dep, key, value)
        return dep

    def test_workflows_list(self):
        self._deployment('d2', workflows={
            'install': {},
            'mock_workflow': {}
        })
        workflows = self.client.workflows.list(id='d2')
        assert {w.name for w in workflows.items} == \
            {'install', 'mock_workflow'}

    def test_workflows_list_workflow_with_params(self):
        parameters = {
            'a': {'type': 'int'},
            'b': {'type': 'string'},
        }
        self._deployment('d3', workflows={
            'mock_workflow': {'parameters': parameters},
        })
        workflows = self.client.workflows.list(id='d3')
        assert len(workflows) == 1
        assert workflows[0].parameters == parameters

    def test_workflows_list_nonexistent(self):
        self._deployment('d1')
        workflows = self.client.workflows.list(id='nonexistent')
        assert workflows.items == []

    def test_workflows_list_group(self):
        self._deployment('d2', workflows={
            'install': {},
            'mock_workflow': {}
        })
        self._deployment('d3', workflows={
            'install': {},
            'uninstall': {},
        })
        self.client.deployment_groups.put('g1', deployment_ids=['d2', 'd3'])
        workflows_for_g1 = self.client.workflows.list(deployment_group_id='g1')
        assert workflows_for_g1
        workflows_for_d2 = self.client.workflows.list(id='d2')
        workflows_for_d3 = self.client.workflows.list(id='d3')
        assert {w.name for w in workflows_for_g1} == {
            w.name for w in itertools.chain(workflows_for_d2, workflows_for_d3)
        }

    def test_workflows_by_filter_rule(self):
        self._deployment(
            'd1',
            workflows={'workflow_d1': {}},
            labels=[('zxc', '1'), ('abc', '1')],
        )
        self._deployment(
            'd2',
            workflows={'workflow_d2': {}},
            labels=[],
        )
        self._deployment(
            'd3',
            workflows={'workflow_d3': {}},
            labels=[('zxc', '2')],
        )

        workflows_by_filter = self.client.workflows.list(
            filter_rules=[FilterRule('zxc', ['1'], LabelsOperator.NOT_ANY_OF,
                                     'label')])
        workflows_for_d3 = self.client.workflows.list(id='d3')
        assert workflows_by_filter.items == workflows_for_d3.items

    def test_workflows_by_filter_id(self):
        self._deployment(
            'd1',
            workflows={'a': {}},
            labels=[('zxc', '1'), ('asd', '1')]
        )
        self._deployment(
            'd2',
            workflows={'a': {},  'mock_workflow': {}},
            labels=[('zxc', '1'), ('asd', '2')]
        )
        self._deployment(
            'd3',
            workflows={'a': {},  'mock_workflow': {}},
            labels=[('zxc', '2'), ('asd', '2')]
        )
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

    def test_workflow_availability_rules_available(self):
        self._deployment(
            'd1',
            workflows={
                'empty': {},
                'no_rule': {'availability_rules': {}},
                'enabled': {'availability_rules': {'available': True}},
                'disabled': {'availability_rules': {'available': False}},
            },
        )
        workflows = self.client.workflows.list(id='d1')
        is_available = {wf.name: wf.is_available for wf in workflows}
        assert is_available['empty']
        assert is_available['no_rule']
        assert is_available['enabled']
        assert not is_available['disabled']
        for wf in workflows:
            if wf.name in ('enabled', 'disabled'):
                assert 'available' in wf.availability_rules

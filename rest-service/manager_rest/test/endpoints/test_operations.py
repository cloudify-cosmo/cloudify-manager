import uuid
from datetime import datetime

import pytest

from cloudify import constants
from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test import base_test
from manager_rest.storage import models


class OperationsTestBase(object):
    def setUp(self):
        super(OperationsTestBase, self).setUp()
        self.execution = self._execution()
        self.bp1 = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )
        self.dep1 = self._deployment('d1')

    def _execution(self, **kwargs):
        return models.Execution(
            created_at=datetime.utcnow(),
            id='execution_{}'.format(uuid.uuid4()),
            is_system_workflow=False,
            workflow_id='install',
            creator=self.user,
            tenant=self.tenant,
            **kwargs
        )

    def _graph(self, **kwargs):
        exc = kwargs.pop('execution', self.execution)
        return models.TasksGraph(
            execution=exc,
            creator=self.user,
            tenant=self.tenant,
            **kwargs
        )

    def _operation(self, **kwargs):
        return models.Operation(
            creator=self.user,
            tenant=self.tenant,
            **kwargs
        )

    def _deployment(self, deployment_id, **kwargs):
        deployment_params = {
            'id': deployment_id,
            'blueprint': self.bp1,
            'scaling_groups': {},
            'creator': self.user,
            'tenant': self.tenant,
        }
        deployment_params.update(kwargs)
        return models.Deployment(**deployment_params)

    def _node(self, node_id, **kwargs):
        node_params = {
            'id': node_id,
            'type': 'type1',
            'number_of_instances': 0,
            'deploy_number_of_instances': 0,
            'max_number_of_instances': 0,
            'min_number_of_instances': 0,
            'planned_number_of_instances': 0,
            'deployment': self.dep1,
            'creator': self.user,
            'tenant': self.tenant,
        }
        node_params.update(kwargs)
        return models.Node(**node_params)

    def _instance(self, instance_id, **kwargs):
        instance_params = {
            'id': instance_id,
            'state': '',
            'creator': self.user,
            'tenant': self.tenant,
        }
        instance_params.update(kwargs)
        if 'node' not in instance_params:
            instance_params['node'] = self._node('node1')
        return models.NodeInstance(**instance_params)


class OperationsTestCase(OperationsTestBase, base_test.BaseServerTestCase):
    def test_operations_created_embedded(self):
        """Create operations when sending the tasks graph

        Operations are embedded in the tasks graph, so that only one request
        is enough to create both the graph and the operations.
        """
        op1 = {
            'id': uuid.uuid4().hex,
            'name': 'op1',
            'dependencies': [],
            'parameters': {},
            'type': 'RemoteWorkflowTask'
        }
        op2 = {
            'id': uuid.uuid4().hex,
            'name': 'op2',
            'dependencies': [],
            'parameters': {},
            'type': 'RemoteWorkflowTask'
        }
        tg = self.client.tasks_graphs.create(
            self.execution.id, name='workflow', operations=[op1, op2])
        ops = self.client.operations.list(tg.id)
        assert len(ops) == 2
        assert {op['id'] for op in ops} == {op1['id'], op2['id']}

    def test_operation_counts(self):
        op1 = {
            'id': uuid.uuid4().hex,
            'name': 'op1',
            'dependencies': [],
            'parameters': {},
            'type': 'RemoteWorkflowTask'
        }
        op2 = {
            'id': uuid.uuid4().hex,
            'name': 'op2',
            'dependencies': [],
            'parameters': {},
            'type': 'RemoteWorkflowTask'
        }
        assert self.execution.finished_operations is None
        assert self.execution.total_operations is None
        self.client.tasks_graphs.create(
            self.execution.id, name='workflow', operations=[op1, op2])
        self.sm.refresh(self.execution)
        assert self.execution.finished_operations == 0
        assert self.execution.total_operations == 2
        self.client.operations.update(op1['id'], constants.TASK_SUCCEEDED)
        self.sm.refresh(self.execution)
        assert self.execution.finished_operations == 1

    def test_list_invalid_filters(self):
        with pytest.raises(CloudifyClientError) as cm:
            self.client.operations.list()
        assert cm.value.status_code == 400

        with pytest.raises(CloudifyClientError) as cm:
            self.client.operations.list(execution_id='nonexistent')
        assert cm.value.status_code == 404

        with pytest.raises(CloudifyClientError) as cm:
            self.client.operations.list(graph_id='nonexistent')
        assert cm.value.status_code == 404

    def test_list_for_graph(self):
        tg1 = self._graph(id='tg-1', name='workflow1')
        tg2 = self._graph(id='tg-2', name='workflow2')
        self._operation(id='op1', tasks_graph=tg1, state='pending')
        self._operation(id='op2', tasks_graph=tg1, state='pending')
        self._operation(id='op3', tasks_graph=tg2, state='pending')

        operations = self.client.operations.list(tg1.id)
        assert len(operations) == 2
        assert {op.id for op in operations} == {'op1', 'op2'}

    def test_list_for_execution(self):
        tg1 = self._graph(id='tg-1', name='workflow1')
        tg2 = self._graph(id='tg-2', name='workflow2')
        self._operation(id='op1', tasks_graph=tg1, state='pending')
        self._operation(id='op2', tasks_graph=tg1, state='pending')
        self._operation(id='op3', tasks_graph=tg2, state='pending')
        exc2 = self._execution()
        tg3 = self._graph(id='tg-3', name='worfklow3', execution=exc2)
        self._operation(id='op4', tasks_graph=tg3, state='pending')

        operations = self.client.operations.list(
            execution_id=self.execution.id)
        assert len(operations) == 3
        assert {op.id for op in operations} == {'op1', 'op2', 'op3'}

    def test_list_state(self):
        tg1 = self._graph(id='g1', name='workflow1')
        self._operation(id='op1', tasks_graph=tg1, state='pending')
        self._operation(id='op2', tasks_graph=tg1, state='started')

        all_ops = self.client.operations.list(graph_id='g1')
        pending = self.client.operations.list(graph_id='g1', state='pending')
        started = self.client.operations.list(graph_id='g1', state='started')
        empty = self.client.operations.list(graph_id='g1', state='nonexistent')

        assert {o.id for o in all_ops} == {'op1', 'op2'}
        assert {o.id for o in pending} == {'op1'}
        assert {o.id for o in started} == {'op2'}
        assert len(empty) == 0

    def test_skip_internal(self):
        tg1 = self._graph(id='g1', name='workflow1')
        self._operation(id='op1', tasks_graph=tg1, state='pending',
                        type='SendNodeEventTask')
        self._operation(id='op2', tasks_graph=tg1, state='started',
                        type='RemoteWorkflowTask')
        self._operation(id='op3', tasks_graph=tg1, state='started',
                        type='SubgraphTask')

        all_ops = self.client.operations.list(graph_id='g1')
        skip = self.client.operations.list(graph_id='g1', skip_internal=True)

        assert {o.id for o in all_ops} == {'op1', 'op2', 'op3'}
        assert {o.id for o in skip} == {'op2', 'op3'}

    def test_get_operation(self):
        tg1 = self._graph(id='g1', name='workflow1')
        self._operation(id='op1', tasks_graph=tg1, state='pending',
                        type='SendNodeEventTask')
        with pytest.raises(CloudifyClientError) as cm:
            self.client.operations.get('nonexistent')
        assert cm.value.status_code == 404
        op = self.client.operations.get('op1')
        assert op.id == 'op1'


class TasksGraphsTestCase(OperationsTestBase, base_test.BaseServerTestCase):
    def test_list_invalid(self):
        with pytest.raises(CloudifyClientError) as cm:
            self.client.tasks_graphs.list(execution_id='nonexistent')
        assert cm.value.status_code == 404

        tgs = self.client.tasks_graphs.list(
            execution_id=self.execution.id, name='nonexistent')
        assert len(tgs) == 0

    def test_list_by_execution(self):
        exc2 = self._execution()
        tg1 = self._graph(id='tg1', execution=self.execution)
        tg2 = self._graph(id='tg2', execution=exc2)
        tgs1 = self.client.tasks_graphs.list(execution_id=self.execution.id)
        tgs2 = self.client.tasks_graphs.list(execution_id=exc2.id)
        assert {t.id for t in tgs1} == {tg1.id}
        assert {t.id for t in tgs2} == {tg2.id}

    def test_list_by_name(self):
        tg1 = self._graph(id='tg1', execution=self.execution, name='wf1')
        tg2 = self._graph(id='tg2', execution=self.execution, name='wf2')
        tgs1 = self.client.tasks_graphs.list(
            execution_id=self.execution.id, name='wf1')
        tgs2 = self.client.tasks_graphs.list(
            execution_id=self.execution.id, name='wf2')
        assert {t.id for t in tgs1} == {tg1.id}
        assert {t.id for t in tgs2} == {tg2.id}

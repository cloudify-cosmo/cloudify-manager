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

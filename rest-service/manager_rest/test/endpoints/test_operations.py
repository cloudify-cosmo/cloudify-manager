import uuid
from datetime import datetime

from cloudify import constants

from manager_rest.test import base_test
from manager_rest.storage import models


class OperationsTestCase(base_test.BaseServerTestCase):

    def setUp(self):
        super(OperationsTestCase, self).setUp()

        self.execution = models.Execution(
            created_at=datetime.utcnow(),
            id='execution_{}'.format(uuid.uuid4()),
            is_system_workflow=False,
            workflow_id='install',
            creator=self.user,
            tenant=self.tenant,
        )

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

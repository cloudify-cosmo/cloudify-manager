#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

from datetime import datetime
from faker import Faker

from flask import g

from cloudify import constants

from manager_rest import server
from manager_rest.test import base_test
from manager_rest.storage import models
from manager_rest.test.attribute import attr


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class OperationsTestCase(base_test.BaseServerTestCase):
    fake = Faker()

    def setUp(self):
        super(OperationsTestCase, self).setUp()
        session = server.db.session
        tenant = g.current_tenant

        user = models.User(username=self.fake.name(), email=self.fake.email())
        session.add(user)
        session.commit()

        self.execution = models.Execution(
            created_at=datetime.utcnow(),
            id='execution_{}'.format(self.fake.uuid4()),
            is_system_workflow=False,
            workflow_id='install',
            creator=user,
            tenant=tenant)
        session.add(self.execution)
        session.commit()

    def test_operations_created_embedded(self):
        """Create operations when sending the tasks graph

        Operations are embedded in the tasks graph, so that only one request
        is enough to create both the graph and the operations.
        """
        op1 = {
            'id': self.fake.uuid4(),
            'name': 'op1',
            'dependencies': [],
            'parameters': {},
            'type': 'RemoteWorkflowTask'
        }
        op2 = {
            'id': self.fake.uuid4(),
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
            'id': self.fake.uuid4(),
            'name': 'op1',
            'dependencies': [],
            'parameters': {},
            'type': 'RemoteWorkflowTask'
        }
        op2 = {
            'id': self.fake.uuid4(),
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

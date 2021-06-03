########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_events_logs
ansi_escape = re.compile(r'\x1b[^m]*m')


@pytest.mark.usefixtures('testmockoperations_plugin')
class ExecutionLoggingTest(AgentlessTestCase):

    def test_execution_logging(self):
        blueprint_path = resource('dsl/execution_logging.yaml')
        deployment, _ = self.deploy_application(blueprint_path)
        for user_cause in [False, True]:
            with self.assertRaises(RuntimeError):
                self.execute_workflow(
                    'execute_operation',
                    deployment_id=deployment.id,
                    parameters={'operation': 'test.op',
                                'operation_kwargs': {'user_cause': user_cause}}
                )
        executions = self.client.executions.list(
            deployment_id=deployment.id,
            workflow_id='execute_operation').items
        no_user_cause_ex_id = [
            e for e in executions
            if not e.parameters['operation_kwargs'].get('user_cause')][0].id
        user_cause_ex_id = [
            e for e in executions
            if e.parameters['operation_kwargs'].get('user_cause')][0].id
        self.do_assertions(self._wait_for_end_events,
                           execution_ids=[no_user_cause_ex_id,
                                          user_cause_ex_id],
                           timeout=120)

        def assert_output():
            events = self._parse_events(no_user_cause_ex_id)
            self.assertIn('INFO_MESSAGE', events)
            self.assertIn('Task failed', events)
            self.assertIn('ERROR_MESSAGE', events)
            self.assertIn('DEBUG_MESSAGE', events)
            self.assertIn('NonRecoverableError: ERROR_MESSAGE', events)
            self.assertNotIn('RuntimeError: ERROR_MESSAGE', events)

            user_cause_events = self._parse_events(user_cause_ex_id)
            self.assertIn('RuntimeError: ERROR_MESSAGE', user_cause_events)

        assert_output()

    def _wait_for_end_events(self, execution_ids):
        for execution_id in execution_ids:
            events = self.client.events.list(
                execution_id=execution_id, event_type='workflow_failed').items
            self.assertGreater(len(events), 0)

    def _parse_events(self, execution_id):
        _events = self.client.events.list(execution_id=execution_id,
                                          include_logs=True)
        events = ''
        for e in _events:
            events += '{}\n'.format(e['message'])
            if e['error_causes']:
                for error_cause in e['error_causes']:
                    events += '{}\n'.format(error_cause['traceback'])
        return events

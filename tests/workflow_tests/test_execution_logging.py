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

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import execute_workflow
from testenv.utils import deploy_application as deploy

ansi_escape = re.compile(r'\x1b[^m]*m')


class ExecutionLoggingTest(TestCase):

    def test_execution_logging(self):
        blueprint_path = resource('dsl/execution_logging.yaml')
        deployment, _ = deploy(blueprint_path)
        for user_cause in [False, True]:
            with self.assertRaises(RuntimeError):
                execute_workflow(
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
                                          user_cause_ex_id])

        def assert_output(verbosity,
                          expect_debug,
                          expect_traceback,
                          expect_rest_logs):
            events = self.cfy.events.list(
                no_user_cause_ex_id, verbosity).stdout
            # When running tests locally (not CI), events returned by the CLI
            # maybe colored, depending on his configuration so we strip ansi
            # escape sequences from retrieved events.
            events = ansi_escape.sub('', events)
            assert_in = self.assertIn
            assert_not_in = self.assertNotIn
            assert_in('INFO: INFO_MESSAGE', events)
            assert_in('Task failed', events)
            assert_in('ERROR_MESSAGE', events)
            debug_assert = assert_in if expect_debug else assert_not_in
            debug_assert('DEBUG: DEBUG_MESSAGE', events)
            trace_assert = assert_in if expect_traceback else assert_not_in
            trace_assert('NonRecoverableError: ERROR_MESSAGE', events)
            assert_not_in('Causes', events)
            assert_not_in('RuntimeError: ERROR_MESSAGE', events)
            rest_assert = assert_in if expect_rest_logs else assert_not_in
            rest_assert('Sending request:', events)
            user_cause_events = self.cfy.events.list(
                user_cause_ex_id,
                verbosity
            )
            causes_assert = assert_in if expect_traceback else assert_not_in
            causes_assert('Causes', user_cause_events)
            causes_assert('RuntimeError: ERROR_MESSAGE', user_cause_events)
        assert_output(verbosity=[],  # sh handles '' as an argument, but not []
                      expect_traceback=False,
                      expect_debug=False,
                      expect_rest_logs=False)
        assert_output(verbosity='-v',
                      expect_traceback=True,
                      expect_debug=False,
                      expect_rest_logs=False)
        assert_output(verbosity='-vv',
                      expect_traceback=True,
                      expect_debug=True,
                      expect_rest_logs=False)
        assert_output(verbosity='-vvv',
                      expect_traceback=True,
                      expect_debug=True,
                      expect_rest_logs=True)

    def _wait_for_end_events(self, execution_ids):
        for execution_id in execution_ids:
            events = self.client.events.list(
                execution_id=execution_id, event_type='workflow_failed').items
            self.assertGreater(len(events), 0)

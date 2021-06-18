########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import uuid
from datetime import datetime, timedelta

import pytest

from integration_tests import AgentTestWithPlugins
from integration_tests.tests.utils import get_resource as resource
from integration_tests.tests.agentless_tests.test_events import (
    _SetAlternateTimezone
)


pytestmark = pytest.mark.group_events_logs


@pytest.mark.usefixtures('dockercompute_plugin')
class TimezoneTest(_SetAlternateTimezone, AgentTestWithPlugins):
    """Events test cases using an alternative timezone (Asia/Jerusalem)."""

    def test_event_timezone(self):
        """Check timestamp values in agent machine.

        The goal of this test case is to verify that when the agent is running
        in a machine where the timezone configuration has been updated, the
        timestamp values are still in the expected range.

        """
        deployment_id = 'd{0}'.format(uuid.uuid4())
        blueprint = 'dsl/agent_tests/dockercompute_timezone.yaml'
        dsl_path = resource(blueprint)

        start_timestamp = '{}Z'.format(datetime.utcnow().isoformat()[:-3])
        self.deploy_application(dsl_path, deployment_id=deployment_id)
        # log storing is async, add a few seconds to allow for that
        stop_timestamp = '{}Z'.format(
            (datetime.utcnow() + timedelta(seconds=3)).isoformat()[:-3])

        logs = self.client.events.list(
            include_logs=True,
            message='Date after timezone configuration:%',
        )
        self.assertEqual(len(logs), 1)
        log = logs[0]
        for field_name in ['timestamp', 'reported_timestamp']:
            self.assertTrue(start_timestamp < log[field_name] < stop_timestamp)

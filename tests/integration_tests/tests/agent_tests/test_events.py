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

from datetime import datetime

from integration_tests import AgentTestWithPlugins
from integration_tests.framework.postgresql import run_query
from integration_tests.tests.utils import get_resource as resource

from manager_rest.flask_utils import get_postgres_conf


class TimezoneTest(AgentTestWithPlugins):

    """Events test cases using an alternative timezone (Asia/Jerusalem)."""

    TIMEZONE = 'Asia/Jerusalem'

    @classmethod
    def setUpClass(cls):
        """Configure database timezone."""
        super(TimezoneTest, cls).setUpClass()

        # Container is launched once per unittest.TestCase class.
        # Timezone configuration just needs to updated at the class level.
        # Between tests cases tables are re-created,
        # but timezone configuration is preserved.
        postgres_conf = get_postgres_conf()
        run_query(
            "ALTER USER {} SET TIME ZONE '{}'"
            .format(postgres_conf.username, cls.TIMEZONE)
        )

    def setUp(self):
        """Update postgres timezone and create a deployment."""
        # Make sure that database timezone is correctly set
        query_result = run_query('SHOW TIME ZONE')
        self.assertEqual(query_result['all'][0][0], self.TIMEZONE)

        super(TimezoneTest, self).setUp()

    def test_event_timezone(self):
        """Check timestamp values in agent machine.

        The goal of this test case is to verify that when the agent is running
        in a machine where the timezone configuration has been updated, the
        timestamp values are still in the expected range.

        """
        deployment_id = str(uuid.uuid4())
        blueprint = 'dsl/dockercompute_timezone.yaml'
        dsl_path = resource(blueprint)

        start_timestamp = '{}Z'.format(datetime.utcnow().isoformat()[:-3])
        self.deploy_application(dsl_path, deployment_id=deployment_id)
        stop_timestamp = '{}Z'.format(datetime.utcnow().isoformat()[:-3])

        logs = self.client.events.list(
            include_logs=True,
            message='Date after timezone configuration:%',
        )
        self.assertEqual(len(logs), 1)
        log = logs[0]
        for field_name in ['timestamp', 'reported_timestamp']:
            self.assertTrue(start_timestamp < log[field_name] < stop_timestamp)

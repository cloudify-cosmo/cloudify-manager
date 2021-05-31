import pytest

from datetime import datetime
from retrying import retry

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_deployments


class ExecutionsSchedulesTest(AgentlessTestCase):

    def test_schedule_execution(self):
        deployment = self.deploy(resource("dsl/empty_blueprint.yaml"))
        self.client.execution_schedules.create(
            'install-every-minute',
            deployment.id,
            'install',
            since=datetime.utcnow().replace(second=0, microsecond=0),
            recurrence='1 min')  # run each HH:MM:00.0
        self.verify_execution_fired(deployment)
        self.client.execution_schedules.delete('install-every-minute',
                                               deployment.id)

    @retry(wait_fixed=1000, stop_max_attempt_number=120)
    def verify_execution_fired(self, deployment):
        # The execution must fire within 2 minutes.
        # if the 1st check_schedules occurs between the creation time and the
        # next :00, the 2nd check (1 min. from then) will run the execution
        executions = self.client.executions.list(deployment_id=deployment.id,
                                                 workflow_id='install')
        self.assertEqual(1, len(executions))

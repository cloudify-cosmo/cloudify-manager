from time import sleep
from datetime import datetime

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource


class ExecutionsSchedulesTest(AgentlessTestCase):

    def test_schedule_execution(self):
        deployment = self.deploy(resource("dsl/empty_blueprint.yaml"))
        self.client.execution_schedules.create(
            'install-every-minute',
            deployment.id,
            'install',
            since=datetime.utcnow().replace(second=0, microsecond=0),
            frequency='1 min')  # run each HH:MM:00.0
        sleep(60)  # the scheduler should fire the execution within 1 min.
        executions = self.client.executions.list(deployment_id=deployment.id,
                                                 workflow_id='install')
        self.assertEqual(1, len(executions))
        self.client.execution_schedules.delete('install-every-minute')

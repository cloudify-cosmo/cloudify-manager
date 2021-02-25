from datetime import datetime

from retrying import retry

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    get_resource as resource,
    wait_for_deployment_creation_to_complete)


class ExecutionsSchedulesTest(AgentlessTestCase):

    def test_schedule_execution(self):
        deployment = self.deploy(resource("dsl/empty_blueprint.yaml"))
        self.client.execution_schedules.create(
            'install-every-minute',
            deployment.id,
            'install',
            since=datetime.utcnow().replace(second=0, microsecond=0),
            frequency='1 min')  # run each HH:MM:00.0
        self.verify_execution_fired(deployment)
        self.client.execution_schedules.delete('install-every-minute')

    def test_upload_blueprint_with_default_schedules(self):
        deployment = self.deploy(resource(
            "dsl/blueprint_with_default_schedules.yaml"))
        wait_for_deployment_creation_to_complete(self.env.container_id,
                                                 deployment.id,
                                                 self.client)
        schedule_from_bp = self.client.execution_schedules.get('sc1')
        self.assertEquals(schedule_from_bp['rule']['frequency'], '1w')
        self.assertEquals(len(schedule_from_bp['all_next_occurrences']), 5)

    @retry(wait_fixed=1000, stop_max_attempt_number=120)
    def verify_execution_fired(self, deployment):
        # The execution must fire within 2 minutes.
        # if the 1st check_schedules occurs between the creation time and the
        # next :00, the 2nd check (1 min. from then) will run the execution
        executions = self.client.executions.list(deployment_id=deployment.id,
                                                 workflow_id='install')
        self.assertEqual(1, len(executions))

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

    def test_create_deployment_with_default_schedules(self):
        deployment = self.deploy(resource(
            "dsl/blueprint_with_default_schedules.yaml"))
        wait_for_deployment_creation_to_complete(self.env.container_id,
                                                 deployment.id,
                                                 self.client)

        sched_ids = [sc['id'] for sc in self.client.execution_schedules.list()]
        sc1_id = '{}_{}'.format(deployment.id, 'sc1')
        sc2_id = '{}_{}'.format(deployment.id, 'sc2')
        self.assertListEqual([sc1_id, sc2_id], sched_ids)

        sc1 = self.client.execution_schedules.get(sc1_id)
        self.assertEquals(sc1['rule']['frequency'], '1w')
        self.assertEquals(len(sc1['all_next_occurrences']), 5)

    def test_update_deployment_with_default_schedules(self):
        deployment = self.deploy(resource(
            "dsl/blueprint_with_default_schedules.yaml"))
        wait_for_deployment_creation_to_complete(self.env.container_id,
                                                 deployment.id,
                                                 self.client)
        sc1_id = '{}_{}'.format(deployment.id, 'sc1')
        sc2_id = '{}_{}'.format(deployment.id, 'sc2')
        sc3_id = '{}_{}'.format(deployment.id, 'sc3')

        sched_ids = [sc['id'] for sc in self.client.execution_schedules.list()]
        self.assertListEqual([sc1_id, sc2_id], sched_ids)
        self.assertEquals(
            'install',
            self.client.execution_schedules.get(sc2_id)['workflow_id'])

        new_blueprint_id = 'updated_schedules'
        self.client.blueprints.upload(
            resource("dsl/blueprint_with_default_schedules2.yaml"),
            new_blueprint_id)
        self.client.deployment_updates.update_with_existing_blueprint(
            deployment.id, new_blueprint_id)
        self._wait_for_deployment_update_to_terminate(deployment.id)

        sched_ids = [sc['id'] for sc in self.client.execution_schedules.list()]
        self.assertListEqual([sc2_id, sc3_id], sched_ids)
        self.assertEquals(
            'uninstall',
            self.client.execution_schedules.get(sc2_id)['workflow_id'])

    @retry(wait_fixed=1000, stop_max_attempt_number=120)
    def verify_execution_fired(self, deployment):
        # The execution must fire within 2 minutes.
        # if the 1st check_schedules occurs between the creation time and the
        # next :00, the 2nd check (1 min. from then) will run the execution
        executions = self.client.executions.list(deployment_id=deployment.id,
                                                 workflow_id='install')
        self.assertEqual(1, len(executions))

    def _wait_for_deployment_update_to_terminate(self, deployment_id):
        # wait for 'update' workflow to finish
        executions = \
            self.client.executions.list(deployment_id=deployment_id,
                                        workflow_id='update')
        for execution in executions:
            self.wait_for_execution_to_end(execution)

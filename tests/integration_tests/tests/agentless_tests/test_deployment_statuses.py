import pytest
from retrying import retry

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    get_resource as resource,
    generate_scheduled_for_date
)

from cloudify.models_states import ExecutionState as Execution
from cloudify.models_states import DeploymentState

pytestmark = pytest.mark.group_deployments


@pytest.mark.usefixtures('cloudmock_plugin')
@pytest.mark.usefixtures('mock_workflows_plugin')
@pytest.mark.usefixtures('testmockoperations_plugin')
class DeploymentStatuses(AgentlessTestCase):

    def _force_deployment_to_be_queued(self, deployment_id):
        execution_1 = self.client.snapshots.create('snapshot_1',
                                                   include_credentials=True,
                                                   include_logs=True,
                                                   include_events=True,
                                                   include_metrics=True,
                                                   queue=True)
        self.wait_for_execution_to_end(execution_1)
        self.manually_update_execution_status(
            Execution.STARTED,
            execution_1.id
        )
        execution_2 = self.execute_workflow(
            workflow_name='install',
            deployment_id=deployment_id,
            wait_for_execution=False,
            queue=True
        )
        return execution_1, execution_2

    def test_deployment_statuses_after_creation(self):
        dsl_path = resource("dsl/basic.yaml")
        deployment = self.deploy(dsl_path)
        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(
            deployment.latest_execution_status,
            DeploymentState.COMPLETED
        )
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.INACTIVE
        )
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.REQUIRE_ATTENTION
        )

    def test_deployment_statuses_after_install(self):
        dsl_path = resource("dsl/basic.yaml")
        deployment = self.deploy(dsl_path)

        self.execute_workflow(workflow_name='install',
                              deployment_id=deployment.id,
                              wait_for_execution=True)

        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(
            deployment.latest_execution_status,
            DeploymentState.COMPLETED
        )
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.ACTIVE
        )
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.GOOD
        )

    def test_deployment_statuses_after_uninstall(self):
        dsl_path = resource("dsl/basic.yaml")
        deployment = self.deploy(dsl_path)

        self.execute_workflow(workflow_name='install',
                              deployment_id=deployment.id,
                              wait_for_execution=True)

        self.execute_workflow(workflow_name='uninstall',
                              deployment_id=deployment.id,
                              wait_for_execution=True)

        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(
            deployment.latest_execution_status,
            DeploymentState.COMPLETED
        )
        # Uninstall mark all node instances as "delete"
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.INACTIVE
        )
        # Since the installation_state is "inactive" then the
        # deployment_status should be "require_attention"
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.REQUIRE_ATTENTION
        )

    def test_deployment_statuses_after_cancel_without_install_nodes(self):
        # Create deployment environment + execute "sleep_with_cancel_support"
        dsl_path = resource("dsl/sleep_workflows.yaml")
        deployment = self.deploy(dsl_path)
        execution = self.execute_workflow(
            workflow_name='simple_sleep',
            deployment_id=deployment.id,
            wait_for_execution=False
        )

        execution = self.client.executions.cancel(execution.id)
        self.wait_for_execution_to_end(execution)

        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(
            deployment.latest_execution_status,
            DeploymentState.CANCELLED
        )
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.INACTIVE
        )
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.REQUIRE_ATTENTION
        )

    def test_deployment_statuses_after_cancel_with_install_nodes(self):
        dsl_path = resource("dsl/sleep_workflows.yaml")
        deployment = self.deploy(dsl_path)
        self.execute_workflow(workflow_name='install',
                              deployment_id=deployment.id,
                              wait_for_execution=True)

        execution = self.execute_workflow(
            workflow_name='simple_sleep',
            deployment_id=deployment.id,
            wait_for_execution=False
        )
        execution = self.client.executions.cancel(execution.id)
        self.wait_for_execution_to_end(execution)

        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(
            deployment.latest_execution_status,
            DeploymentState.CANCELLED
        )
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.ACTIVE
        )
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.GOOD
        )

    def test_deployment_statuses_during_cancelling_without_install_nodes(self):
        # Create deployment environment + execute "sleep_with_cancel_support"
        dsl_path = resource("dsl/sleep_workflows.yaml")
        deployment = self.deploy(dsl_path)
        execution = self.execute_workflow(
            workflow_name='simple_sleep',
            deployment_id=deployment.id,
            wait_for_execution=False
        )

        self.client.executions.cancel(execution.id)
        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(
            deployment.latest_execution_status,
            DeploymentState.IN_PROGRESS
        )
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.INACTIVE
        )
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.IN_PROGRESS
        )

    def test_deployment_statuses_during_cancelling_with_install_nodes(self):
        dsl_path = resource("dsl/sleep_workflows.yaml")
        deployment = self.deploy(dsl_path)
        self.execute_workflow(workflow_name='install',
                              deployment_id=deployment.id,
                              wait_for_execution=True)

        execution = self.execute_workflow(
            workflow_name='simple_sleep',
            deployment_id=deployment.id,
            wait_for_execution=False
        )

        self.client.executions.cancel(execution.id)
        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(
            deployment.latest_execution_status,
            DeploymentState.IN_PROGRESS
        )
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.ACTIVE
        )
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.IN_PROGRESS
        )

    def test_deployment_statuses_during_kill_cancelling(self):
        dsl_path = resource("dsl/sleep_workflows.yaml")
        deployment = self.deploy(dsl_path)
        self.execute_workflow(workflow_name='install',
                              deployment_id=deployment.id,
                              wait_for_execution=True)

        execution = self.execute_workflow(
            workflow_name='simple_sleep',
            deployment_id=deployment.id,
            wait_for_execution=False
        )

        self.client.executions.cancel(execution.id, kill=True)
        deployment = self.client.deployments.get(deployment.id)
        self.assertIn(
            deployment.latest_execution_status,
            [DeploymentState.IN_PROGRESS, DeploymentState.CANCELLED]
        )
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.ACTIVE
        )
        if deployment.latest_execution_status == DeploymentState.CANCELLED:
            self.assertEqual(
                deployment.deployment_status,
                DeploymentState.GOOD
            )
        else:
            self.assertEqual(
                deployment.deployment_status,
                DeploymentState.IN_PROGRESS
            )

    def test_deployment_statuses_after_failed_workflow(self):
        dsl_path = resource('dsl/workflow_api.yaml')
        deployment = self.deploy(dsl_path)
        self.execute_workflow(workflow_name='install',
                              deployment_id=deployment.id,
                              wait_for_execution=True)

        with self.assertRaises(RuntimeError):
            self.execute_workflow(
                workflow_name='execute_operation',
                deployment_id=deployment.id,
                parameters={
                    'operation': 'test.fail',
                    'node_ids': ['test_node']
                },
                wait_for_execution=True
            )

        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(
            deployment.latest_execution_status,
            DeploymentState.FAILED
        )
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.ACTIVE
        )
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.REQUIRE_ATTENTION
        )

    def test_deployment_statuses_for_scheduled_execution(self):
        dsl_path = resource("dsl/basic.yaml")
        deployment = self.deploy(dsl_path)
        deployment = self.client.deployments.get(deployment.id)
        scheduled_time = generate_scheduled_for_date()
        execution = self.client.executions.start(deployment_id=deployment.id,
                                                 workflow_id='install',
                                                 schedule=scheduled_time)
        self.assertEqual(Execution.SCHEDULED, execution.status)
        self.assertEqual(
            deployment.latest_execution_status,
            DeploymentState.COMPLETED
        )
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.INACTIVE
        )
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.REQUIRE_ATTENTION
        )
        # Wait for exec to 'wake up'
        execution = self.wait_for_scheduled_execution_to_fire(deployment.id)
        self.wait_for_execution_to_end(execution)
        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(
            deployment.latest_execution_status,
            DeploymentState.COMPLETED,
        )
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.ACTIVE,
        )
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.GOOD,
        )

    def test_deployment_statuses_after_queued_execution_finish(self):
        dsl_path = resource("dsl/basic.yaml")
        deployment = self.deploy(dsl_path)
        exe1, exe2 = self._force_deployment_to_be_queued(deployment.id)

        self.client.executions.update(exe1.id, Execution.TERMINATED)
        queued_execution = self.client.executions.get(exe2.id)
        self.wait_for_execution_to_end(queued_execution)

        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(
            deployment.latest_execution_status,
            DeploymentState.COMPLETED
        )
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.ACTIVE
        )
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.GOOD
        )

    def test_deployment_statuses_after_dry_run(self):
        dsl_path = resource("dsl/basic.yaml")
        _, execution_id = self.deploy_application(dsl_path,
                                                  wait_for_execution=True,
                                                  dry_run=True)

        execution = self.client.executions.get(execution_id)
        deployment = self.client.deployments.get(execution.deployment_id)
        self.assertEqual(
            deployment.latest_execution_status,
            DeploymentState.COMPLETED,
        )
        self.assertEqual(
            deployment.installation_status,
            DeploymentState.INACTIVE,
        )
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.REQUIRE_ATTENTION,
        )

    @retry(wait_fixed=1000, stop_max_attempt_number=120)
    def wait_for_scheduled_execution_to_fire(self, deployment_id):
        # The execution must fire within 2 minutes.
        # if the 1st check_schedules occurs between the creation time and the
        # next :00, the 2nd check (1 min. from then) will run the execution
        executions = self.client.executions.list(deployment_id=deployment_id,
                                                 workflow_id='install',
                                                 _all_tenants=True)
        self.assertEqual(1, len(executions))
        return executions[0]

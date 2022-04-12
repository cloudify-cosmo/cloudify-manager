import subprocess

import pytest
import retrying

from integration_tests import AgentTestCase

pytestmark = pytest.mark.group_workflows


@pytest.mark.usefixtures('cloudmock_plugin')
@pytest.mark.usefixtures('dockercompute_plugin')
class TestAgentCancel(AgentTestCase):
    def test_kill_cancel(self):
        """Check that kill-cancel does kill operations

        Run operations that take a long time, kill-cancel the execution,
        and assert that the operation processes exist no longer (eventually,
        it's all async).
        """
        blueprint_path = self.make_yaml_file("""
tosca_definitions_version: cloudify_dsl_1_3

imports:
    - cloudify/types/types.yaml
    - plugin:cloudmock
    - plugin:dockercompute

node_templates:
    agent_node:
        type: cloudify.nodes.docker.Compute
        interfaces:
            test:
                op:
                    implementation: cloudmock.cloudmock.tasks.store_pid
                    executor: host_agent
    mgmtworker_node:
        type: cloudify.nodes.Root
        interfaces:
            test:
                op:
                    implementation: cloudmock.cloudmock.tasks.store_pid
                    executor: central_deployment_agent

""")
        dep, _ = self.deploy_application(blueprint_path)

        pids = {'agent_node': None, 'mgmtworker_node': None}
        exc = self.client.executions.start(
            deployment_id=dep.id,
            workflow_id='execute_operation',
            parameters={'operation': 'test.op'},
        )

        @retrying.retry(wait_fixed=500, stop_max_attempt_number=120)
        def wait_for_exec_to_start():
            """Wait for the execution to start and store PIDs

            The execution will store PIDs as runtime-props when the operations
            actually run, which is going to take on the order of seconds
            normally, but could take a bit more - the agent will have to
            install the plugin.
            """
            node_instances = self.client.node_instances.list()
            for ni in node_instances:
                # this will keyerror out (and be retried) if the operation
                # didnt run yet
                pids[ni.node_id] = ni.runtime_properties['pid']

        wait_for_exec_to_start()
        assert None not in pids.values()

        self.client.executions.cancel(exc.id, kill=True)

        @retrying.retry(wait_fixed=500, stop_max_attempt_number=60)
        def wait_for_cancel():
            """Wait for the operation processes to be dead.

            This should take on the order of seconds.
            """
            for pid in pids.values():
                # ps will return nonzero when the pid doesn't exist
                with pytest.raises(subprocess.CalledProcessError):
                    self.execute_on_manager(['ps', str(pid)])

        wait_for_cancel()

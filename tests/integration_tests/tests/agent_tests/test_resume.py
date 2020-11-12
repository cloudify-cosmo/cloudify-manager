########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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
from contextlib import contextmanager

import pytest

from integration_tests import AgentTestCase
from integration_tests.framework import docker
from integration_tests.tests.utils import get_resource as resource


# log messages that are emitted by cloudmock.tasks.task_agent. We're waiting
# on those to know when to stop services in the tests.
BEFORE_MESSAGE = 'BEFORE SLEEP'
AFTER_MESSAGE = 'AFTER SLEEP'


@pytest.mark.usefixtures('cloudmock_plugin')
class TestResumeMgmtworker(AgentTestCase):
    def _start_execution(self, deployment, operation, wait_seconds=20):
        return self.execute_workflow(
            workflow_name='execute_operation',
            wait_for_execution=False,
            deployment_id=deployment.id,
            parameters={'operation': operation,
                        'run_by_dependency_order': True,
                        'operation_kwargs': {
                            'wait_seconds': wait_seconds
                        }})

    def _detach_agents(self):
        """Detach agents from the mgmtworker.

        On systemd, agents spawned by the mgmtworker still belong to the
        mgmtworker cgroup, and are also killed when the mgmtworker stops.
        Detach them from that cgroup by attaching them to another one
        so that they can stay up when we stop the mgmtworker.

        To do that, figure out the agent PIDs, and put them into
        the other-cgroup-dir/tasks file.
        """
        if self._is_supervisord_command():
            return
        agent_pids = docker.execute(self.env.container_id, [
            'pgrep', '-f', 'agent_host'
        ]).splitlines()
        for pid in agent_pids:
            if not pid:
                continue
            docker.execute(self.env.container_id, [
                'bash', '-c',
                'echo {0} > /sys/fs/cgroup/systemd/tasks'.format(pid)
            ])

    def _is_supervisord_command(self):
        return self.get_service_management_command() != 'systemctl'

    @contextmanager
    def update_stopasgroup(self):
        """
        This context mananger used in order to update the mgmtworker
        configuration in order to disable stopasgroup option so that we can
        avoid kill processes already started by mgmtworker which allows us
        to simulate host agent operation
        """
        try:
            # Disable the stopasgroup option from mgmtworker configuration so
            # that we can avoid killing the host agent and task operation
            # from being stopped since the host agent and mgmtworker running
            # inside the same container. This is only relevant for supervisord
            self._toggle_mgmtworker_stopasgroup_option('true', 'false')
            yield
        finally:
            # Enable the stopasgroup again
            self._toggle_mgmtworker_stopasgroup_option('false', 'true')

    def _toggle_mgmtworker_stopasgroup_option(self, old_value, new_value):
        if self._is_supervisord_command():
            self.execute_on_manager(
                "sed -i 's/stopasgroup={0}/stopasgroup={1}/g' "
                "/etc/supervisord.d/mgmtworker.cloudify.conf"
                "".format(old_value, new_value)
            )
            self.execute_on_manager(
                'supervisorctl -c /etc/supervisord.conf reread')
            self.execute_on_manager(
                'supervisorctl -c /etc/supervisord.conf update')

    def _stop_mgmtworker(self):
        self.logger.info('Stopping mgmtworker')
        service_command = self.get_service_management_command()
        self.execute_on_manager(
            '{0} stop cloudify-mgmtworker'.format(service_command)
        )

    def _start_mgmtworker(self):
        self.logger.info('Starting mgmtworker')
        service_command = self.get_service_management_command()
        self.execute_on_manager(
            '{0} start cloudify-mgmtworker'.format(service_command)
        )

    def test_resume_agent_op(self):
        with self.update_stopasgroup():
            deployment_id = 'd{0}'.format(uuid.uuid4())
            dsl_path = resource('dsl/resumable_agent.yaml')
            deployment, execution_id = self.deploy_application(
                dsl_path, deployment_id=deployment_id)
            self._detach_agents()
            execution = self._start_execution(deployment, 'interface1.op1')
            # wait until the agent starts executing operations
            self.wait_for_event(execution, BEFORE_MESSAGE)
            instance = self.client.node_instances.list(
                node_id='agent_host', deployment_id=deployment.id)[0]
            self.assertFalse(instance.runtime_properties['resumed'])

            # Stop mgmtworker while the operation is executed by host_agent
            self._stop_mgmtworker()
            if self._is_supervisord_command():
                # kill the execution operation process since its not going to
                # be killed by the mgmtworker after we disable the stopasgroup
                # option
                self.execute_on_manager(
                    'pkill -f task-cloudify.execute_operation'
                )

            # Start mgmtworker
            self._start_mgmtworker()
            # check that we resume waiting for the agent operation
            self.wait_for_event(execution, AFTER_MESSAGE)
            self.wait_for_execution_to_end(execution)
            instance = self.client.node_instances.get(instance.id)
            self.assertTrue(instance.runtime_properties['resumed'])

    def test_resume_agent_op_finished(self):
        with self.update_stopasgroup():
            deployment_id = 'd{0}'.format(uuid.uuid4())
            dsl_path = resource('dsl/resumable_agent.yaml')
            deployment, execution_id = self.deploy_application(
                dsl_path, deployment_id=deployment_id)
            self._detach_agents()

            execution = self._start_execution(
                deployment, 'interface1.op1', wait_seconds=10)

            # wait until the agent starts executing operations
            self.wait_for_event(execution, BEFORE_MESSAGE)

            self._stop_mgmtworker()
            if self._is_supervisord_command():
                # kill the execution operation process since its not going to
                # be killed by the mgmtworker after we disable the stopasgroup
                # option
                self.execute_on_manager(
                    'pkill -f task-cloudify.execute_operation'
                )
            # wait for the agent to finish executing the operation
            while True:
                instance = self.client.node_instances.list(
                    node_id='agent_host', deployment_id=deployment.id)[0]
                if instance.runtime_properties['resumed']:
                    break

            self._start_mgmtworker()
            # check that we resume waiting for the agent operation
            self.wait_for_execution_to_end(execution)

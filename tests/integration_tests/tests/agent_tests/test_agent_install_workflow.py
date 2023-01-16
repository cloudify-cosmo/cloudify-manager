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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import uuid
import pytest
import retrying

from integration_tests import AgentTestWithPlugins
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_agents


@pytest.mark.usefixtures('dockercompute_plugin')
class TestWorkflow(AgentTestWithPlugins):
    def _get_queues(self, vhost=None):
        cmd = ['rabbitmqctl', 'list_queues', '-s']
        if vhost:
            cmd += ['-p', vhost]
        output = self.execute_on_manager(cmd)
        return {line.split()[0] for line in output.splitlines()}

    def _get_exchanges(self, vhost=None):
        cmd = ['rabbitmqctl', 'list_exchanges', '-s']
        if vhost:
            cmd += ['-p', vhost]
        output = self.execute_on_manager(cmd)
        return {line.split()[0] for line in output.splitlines()}

    def test_amqp_queues_list(self):
        """There's no additional queues after uninstalling the agent.

        We've seen queue leaks in the past, where queues or exchanges
        were not deleted. Check that uninstalling the agent, also removes
        its AMQP resources.
        """
        vhost = 'rabbitmq_vhost_default_tenant'
        deployment_id = 'd{0}'.format(uuid.uuid4())

        main_queues = self._get_queues()
        main_exchanges = self._get_exchanges()
        tenant_queues = self._get_queues(vhost)
        tenant_exchanges = self._get_exchanges(vhost)

        self.deploy_application(
            resource('dsl/agent_tests/with_agent.yaml'),
            deployment_id=deployment_id
        )

        # retrying these assertions (and the post-undeploy ones) because
        # removing queues in our BlockingRequestResponseHandler in AMQP
        # isn't synchronous, and we might just get more queues than we
        # expected - this will however converge very quickly
        # (normally sub-second)
        @retrying.retry(wait_fixed=1000, stop_max_attempt_number=10)
        def _post_deploy_assertions():
            # installing the agent does nothing for the / vhost
            assert self._get_queues() == main_queues
            assert self._get_exchanges() == main_exchanges

            # after installing the agent, there's 2 new queues and at least
            # 1 new exchange
            agent_queues = self._get_queues(vhost) - tenant_queues
            agent_exchanges = self._get_exchanges(vhost) - tenant_exchanges
            assert len(agent_queues) == 2, (
                "expected 2 agent queues, but found {0}: {1}"
                .format(len(agent_queues), agent_queues)
            )
            assert any(queue.endswith('_service') for queue in agent_queues)
            assert any(queue.endswith('_operation') for queue in agent_queues)
            assert any(exc.startswith('agent_host') for exc in agent_exchanges)
            # we already checked that there's an agent exchange, but there
            # might also exist a logs exchange and an events exchange,
            # depending if any events or logs were sent or not
            assert len(agent_exchanges) in (1, 2, 3)

        _post_deploy_assertions()

        self.undeploy_application(deployment_id)

        @retrying.retry(wait_fixed=1000, stop_max_attempt_number=10)
        def _post_undeploy_assertions():
            main_queues = self._get_queues()
            main_exchanges = self._get_exchanges()
            tenant_queues = self._get_queues(vhost)
            agent_exchanges = self._get_exchanges(vhost) - tenant_exchanges
            # after uninstalling the agent, there's still no new queues on
            # the / vhost
            assert self._get_queues() == main_queues
            assert self._get_exchanges() == main_exchanges
            # there's no queues left over
            assert self._get_queues(vhost) == tenant_queues
            # the logs and events exchanges will still exist, but the agent
            # exchange must have been deleted
            assert not any(exc.startswith('agent_host')
                           for exc in agent_exchanges)

        _post_undeploy_assertions()

    def test_deploy_with_agent_worker(self):
        # In 4.2, the default (remote) agent installation path only requires
        # the "create" operation
        install_events = [
            "Task succeeded 'cloudify_agent.installer.operations.create'"
        ]
        uninstall_events = [
            "Task succeeded 'cloudify_agent.installer.operations.delete'"
        ]
        self._test_deploy_with_agent_worker(
            'dsl/agent_tests/with_agent.yaml',
            install_events,
            uninstall_events
        )

    def _test_deploy_with_agent_worker(self,
                                       blueprint,
                                       install_events,
                                       uninstall_events):
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource(blueprint)
        _, execution_id = self.deploy_application(
            dsl_path,
            deployment_id=deployment_id
        )

        events = self.client.events.list(execution_id=execution_id,
                                         sort='timestamp')
        filtered_events = [event['message'] for event in events if
                           event['message'] in install_events]

        # Make sure the install events were called (in the correct order)
        self.assertListEqual(install_events, filtered_events)

        execution_id = self.undeploy_application(deployment_id)

        events = self.client.events.list(execution_id=execution_id,
                                         sort='timestamp')
        filtered_events = [event['message'] for event in events if
                           event['message'] in uninstall_events]

        # Make sure the uninstall events were called (in the correct order)
        self.assertListEqual(uninstall_events, filtered_events)

    @pytest.mark.usefixtures('target_aware_mock_plugin')
    def test_deploy_with_operation_executor_override(self):
        setup_deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource('dsl/agent_tests/operation_executor_override.yaml')
        _, execution_id = self.deploy_application(
            dsl_path,
            deployment_id=setup_deployment_id
        )

        webserver_nodes = self.client.node_instances.list(
            deployment_id=setup_deployment_id,
            node_id='webserver'
        )
        self.assertEqual(1, len(webserver_nodes))
        webserver_node = webserver_nodes[0]

        webserver_host_node = self.client.node_instances.list(
            deployment_id=setup_deployment_id,
            node_id='webserver_host'
        )[0]

        create_invocation = webserver_node.runtime_properties['create']
        expected_create_invocation = {'target': webserver_host_node.id}
        self.assertEqual(expected_create_invocation, create_invocation)

        start_invocation = webserver_node.runtime_properties['start']
        expected_start_invocation = {'target': 'cloudify.management'}
        self.assertEqual(expected_start_invocation, start_invocation)

    def test_script_executor(self):
        """Check that script-plugin scripts use the correct executor.

        When the executor is not provided, the 'auto' executor kind will
        detect whether the node-instance is on an agent or not, and
        run its operations on the relevant executor.

        In this case, we have a node type that has two instances - one
        contained_in a compute, and one that isn't. The one in a compute
        does run on the agent, and the other one runs on the mgmtworker.
        """
        bp = """
tosca_definitions_version: cloudify_dsl_1_5
imports:
    - cloudify/types/types.yaml
    - plugin:dockercompute
node_types:
    t1:
        derived_from: cloudify.nodes.Root
        interfaces:
            cloudify.interfaces.lifecycle:
                create: |
                    ctx instance runtime-properties create "${AGENT_NAME:-mgmtworker}"
                start: |
                    import os
                    from cloudify import ctx
                    ctx.instance.runtime_properties['start'] = \
                        os.environ.get('AGENT_NAME') or 'mgmtworker'
node_templates:
    agent_host:
        type: cloudify.nodes.docker.Compute
    n1:
        type: t1
        relationships:
            - type: cloudify.relationships.contained_in
              target: agent_host
    n2:
        type: t1
"""  # NOQA
        self.upload_blueprint_resource(
            self.make_yaml_file(bp),
            blueprint_id='bp1',
        )
        dep, _ = self.deploy_application(self.make_yaml_file(bp))
        agents = self.client.agents.list()
        n1_inst = self.client.node_instances.list(
            deployment_id=dep.id, node_id='n1')
        n2_inst = self.client.node_instances.list(
            deployment_id=dep.id, node_id='n2')
        self.undeploy_application(dep.id)

        assert len(agents) == 1
        assert len(n1_inst) == 1
        assert len(n2_inst) == 1
        agent_id = agents[0].id
        assert n1_inst[0].runtime_properties == \
            {'create': agent_id, 'start': agent_id}
        assert n2_inst[0].runtime_properties == \
            {'create': 'mgmtworker', 'start': 'mgmtworker'}

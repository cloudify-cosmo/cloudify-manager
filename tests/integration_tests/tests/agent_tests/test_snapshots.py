########
# Copyright (c) 2013-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import time
import uuid
import pytest

from integration_tests import AgentTestCase
from cloudify.models_states import AgentState
from integration_tests.tests.utils import get_resource as resource
from integration_tests.framework.flask_utils import reset_storage

pytestmark = pytest.mark.group_snapshots

CREATE_SNAPSHOT_SUCCESS_MSG =\
    "'create_snapshot' workflow execution succeeded"
RESTORE_SNAPSHOT_SUCCESS_MSG =\
    "'restore_snapshot' workflow execution succeeded"


class TestSnapshots(AgentTestCase):

    def _deploy_with_agents(self, states):
        deployments = []
        execution_ids = []
        for state in states:
            deployment, execution = self.deploy_application(
                resource("dsl/agent_tests/with_agent.yaml"),
                wait_for_execution=False,
            )
            deployments.append(deployment)
            execution_ids.append(execution)

        for execution_id in execution_ids:
            exc = self.client.executions.get(execution_id)
            self.wait_for_execution_to_end(exc)

        for deployment, state in zip(deployments, states):
            agent = self.client.agents.list(deployment_id=deployment.id)
            self.client.agents.update(agent.items[0].id, state)

        self.assertEqual(
            len(self.client.agents.list(state=states).items),
            len(states),
        )
        return deployments

    def _create_snapshot(self):
        snapshot_id = 's{0}'.format(uuid.uuid4())
        execution = self.client.snapshots.create(snapshot_id, False, False)
        self.wait_for_execution_to_end(execution)
        return snapshot_id

    def _undeploy(self, states, deployments):
        executions = [
            self.client.executions.start(deployment.id, 'uninstall')
            for deployment in deployments
        ]
        for execution in executions:
            self.wait_for_execution_to_end(execution)

        for deployment in deployments:
            self.delete_deployment(deployment.id, validate=True)

        self.assertEqual(len(self.client.agents.list(state=states).items), 0)

    def _restore_snapshot(self, states, deployments, snapshot_id):
        # force restore since the manager will be unclean between tests
        execution = self.client.snapshots.restore(snapshot_id, force=True)
        self.wait_for_event(execution, RESTORE_SNAPSHOT_SUCCESS_MSG)
        # still give some time for the post-restore actions to run
        time.sleep(15)
        for state in states:
            self.assertEqual(len(self.client.agents.list(state=state)), 1)
        agent_list = self.client.agents.list(state=states)
        self.assertEqual(len(agent_list.items), len(states))
        self.assertEqual({agent['deployment'] for agent in agent_list.items},
                         {deployment.id for deployment in deployments})

    def _deploy_with_agents_multitenant(self, new_client):
        self.deploy_application(resource("dsl/agent_tests/with_agent.yaml"),
                                deployment_id='mt_default')
        self.deploy(resource("dsl/agent_tests/with_agent.yaml"),
                    deployment_id='mt_new',
                    client=new_client)
        execution = new_client.executions.start('mt_new', 'install')
        self.wait_for_execution_to_end(execution, client=new_client)
        agents_list = self.client.agents.list(
            _all_tenants=True, deployment_id=['mt_default', 'mt_new'])
        self.assertEqual(len(agents_list.items), 2)

    def _undeploy_multitenant(self, new_client):
        self.undeploy_application('mt_default', is_delete_deployment=True)
        uninstall2 = new_client.executions.start('mt_new', 'uninstall')
        self.wait_for_execution_to_end(uninstall2, client=new_client)
        self.delete_deployment('mt_new', validate=True, client=new_client)
        agents_list = self.client.agents.list(
            _all_tenants=True, deployment_id=['mt_default', 'mt_new'])
        self.assertEqual(len(agents_list.items), 0)

    def _restore_snapshot_multitenant(self, snapshot_id):
        execution = self.client.snapshots.restore(snapshot_id, force=True)
        self.wait_for_event(execution, RESTORE_SNAPSHOT_SUCCESS_MSG)
        time.sleep(15)
        agents_list = self.client.agents.list(
            _all_tenants=True, deployment_id=['mt_default', 'mt_new'])
        self.assertEqual(len(agents_list.items), 2)
        self.assertEqual({agent['deployment'] for agent in agents_list.items},
                         {'mt_default', 'mt_new'})
        self.assertEqual({agent['tenant_name'] for agent in agents_list.items},
                         {'default_tenant', 'mike'})

    def test_snapshot_with_agents(self):
        states = [AgentState.STARTED, AgentState.CREATING]
        deployments = self._deploy_with_agents(states)
        self.assertEqual(len(self.client.agents.list().items), 2)
        snapshot_id = self._create_snapshot()

        downloaded_snapshot = os.path.join(self.workdir, 'snapshot.zip')
        self.client.snapshots.download(
            snapshot_id,
            output_file=downloaded_snapshot,
        )

        reset_storage(self.env)
        self.client.snapshots.upload(downloaded_snapshot, snapshot_id)
        self._restore_snapshot(states, deployments, snapshot_id)

        deps = self.client.deployments.list()
        for dep in deps:
            self.execute_workflow('install_new_agents', dep.id)

        # unlike the other tenant tests, in this one we FIRST reset + restore,
        # and only then undeploy. This checks that agent connectivity is
        # still available after that reset + restore
        agents = self.client.agents.list()
        # there's 4 agents, but 2 of those are the "upgraded" ones
        self.assertEqual(len(agents), 4)
        assert sum(
            agent.state == AgentState.UPGRADED for agent in agents
        ) == 2
        self._undeploy(states, deployments)
        self.assertEqual(len(self.client.agents.list().items), 0)

    def test_snapshot_with_failed_agents(self):
        states = [AgentState.STOPPED, AgentState.DELETED, AgentState.FAILED]
        deployments = self._deploy_with_agents(states)

        snapshot_id = self._create_snapshot()
        downloaded_snapshot = os.path.join(self.workdir, 'snapshot.zip')
        self.client.snapshots.download(
            snapshot_id,
            output_file=downloaded_snapshot,
        )

        self._undeploy(states, deployments)

        reset_storage(self.env)
        self.client.snapshots.upload(downloaded_snapshot, snapshot_id)
        self._restore_snapshot(states, deployments, snapshot_id)

    def test_snapshot_with_agents_multitenant(self):
        self.client.tenants.create('mike')
        mike_client = self.create_rest_client(tenant='mike')
        self._deploy_with_agents_multitenant(mike_client)

        snapshot_id = self._create_snapshot()
        downloaded_snapshot = os.path.join(self.workdir, 'snapshot.zip')
        self.client.snapshots.download(
            snapshot_id,
            output_file=downloaded_snapshot,
        )

        self._undeploy_multitenant(mike_client)

        reset_storage(self.env)
        self.client.snapshots.upload(downloaded_snapshot, snapshot_id)
        self._restore_snapshot_multitenant(snapshot_id)

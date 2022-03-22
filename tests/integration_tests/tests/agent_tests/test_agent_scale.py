import pytest

from integration_tests import AgentTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_agents


class TestScaleWithAgents(AgentTestCase):
    def test_failed_scale_with_agents(self):
        """After a failed scale, pre-existing agent entries aren't removed"""
        deployment1, _ = self.deploy_application(resource(
            "dsl/agent_tests/with_agent_scalable.yaml"), deployment_id='d1')
        dep_id = deployment1.id
        instances = self.client.node_instances.list(deployment_id=dep_id)
        assert len(instances) == 1
        agent_list = self.client.agents.list()
        assert len(agent_list.items) == 1
        exc = self.client.executions.start(
            deployment_id=dep_id,
            workflow_id='scale',
            parameters={
                'delta': 1,
                'scalable_entity_name': 'group1',
            },
        )
        with pytest.raises(RuntimeError):
            self.wait_for_execution_to_end(exc)

        instances = self.client.node_instances.list(deployment_id=dep_id)
        assert len(instances) == 1
        agent_list = self.client.agents.list()
        assert len(agent_list.items) == 1
        self.undeploy_application(dep_id)

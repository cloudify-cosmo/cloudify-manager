import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    get_resource as resource,
    wait_for_blueprint_upload,
)


pytestmark = pytest.mark.benchmarks


@pytest.mark.usefixtures('bench')
class BenchmarkExecutionsTest(AgentlessTestCase):
    def test_thousand_deployments(self):
        # reset in case another test changed it
        self.client.manager.put_config('max_concurrent_workflows', 20)

        dsl_path = resource("benchmarks/one_node_bp/bp.yaml")
        self.client.blueprints.upload(dsl_path, 'bp1')
        wait_for_blueprint_upload('bp1', self.client)

        self.bench.start()
        self.client.deployment_groups.put(
            'g1',
            blueprint_id='bp1',
            new_deployments=[{}] * 1000,  # let a thousand deployments bloom
        )
        installs = self.client.execution_groups.start('g1', 'install')
        self.wait_for_execution_to_end(
            installs, is_group=True, timeout_seconds=3600)
        self.bench.stop()

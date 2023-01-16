import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource
from cloudify_rest_client.exceptions import CloudifyClientError

pytestmark = pytest.mark.group_premium


class SecretsProvidersTest(AgentlessTestCase):
    def test_get_secret_from_local_provider(self):
        dsl_path = resource("dsl/basic_get_secret.yaml")
        error_msg = "Required secrets: .* don't exist in this tenant"
        self.assertRaisesRegex(
            CloudifyClientError,
            error_msg,
            self.deploy_application,
            dsl_path
        )

        # Manage to create deployment after creating the secret
        self.client.secrets_providers.create(
            'local_provider',
            'local',
        )
        self.client.secrets.create(
            'port',
            '8080',
            provider='local_provider',
        )
        deployment, _ = self.deploy_application(dsl_path)

        nodes = self.client.nodes.list(
            deployment_id=deployment.id,
        )
        assert nodes[0].properties['port'] == {'get_secret': 'port'}

        nodes = self.client.nodes.list(
            deployment_id=deployment.id,
            evaluate_functions=True,
        )
        assert nodes[0].properties['port'] == '8080'

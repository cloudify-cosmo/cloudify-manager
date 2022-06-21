import uuid
import pytest
from string import ascii_lowercase, ascii_uppercase, punctuation

from integration_tests import AgentlessTestCase
from integration_tests.tests import utils
from cloudify_rest_client.exceptions import CloudifyClientError

pytestmark = pytest.mark.group_general


@pytest.mark.usefixtures('cloudmock_plugin')
class TestPasswordSecret(AgentlessTestCase):

    def test_create_password_secret(self):

        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = utils.get_resource('dsl/password_secret_type.yaml')
        self.deploy_application(dsl_path, deployment_id=deployment_id)
        password_ni_id = self.client.node_instances.list(
            deployment_id=deployment_id)[0].id
        password_runtime_props = self.client.node_instances.get(
            password_ni_id).runtime_properties
        secret_name = password_runtime_props['secret_name']
        self.assertEqual(password_runtime_props['password'],
                         {"get_secret": secret_name})
        created_secret = self.client.secrets.get(secret_name)
        created_password = created_secret.value

        assert len(created_password) == 8
        num_uppercase, num_lowercase, num_symbols = 0, 0, 0
        for ch in created_password:
            if ch in ascii_uppercase:
                num_uppercase += 1
            if ch in ascii_lowercase:
                num_lowercase += 1
            if ch in punctuation + ' ':
                num_symbols += 1
        assert num_uppercase >= 1
        assert num_uppercase >= 1
        assert num_symbols == 0

        self.undeploy_application(deployment_id)
        self.assertRaises(CloudifyClientError,
                          self.client.secrets.get,
                          secret_name)

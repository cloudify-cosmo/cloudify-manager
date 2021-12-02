import pytest

from cloudify_rest_client.exceptions import CloudifyClientError, ForbiddenError

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_deployments


class BlueprintChownTest(AgentlessTestCase):
    BLUEPRINT_ID = 'bp'
    BLUEPRINT_FILENAME = 'empty_blueprint.yaml'

    def test_successful(self):
        self.client.blueprints.upload(
            resource('dsl/{}'.format(self.BLUEPRINT_FILENAME)),
            entity_id=self.BLUEPRINT_ID)
        self.client.users.create('user1', 'password1', 'default')
        self.client.blueprints.update(self.BLUEPRINT_ID, {'creator': 'user1'})

        blueprint = self.client.blueprints.get(self.BLUEPRINT_ID)
        assert blueprint.get('created_by') == 'user1'
        with self.assertRaisesRegex(CloudifyClientError, 'has blueprints'):
            self.client.users.delete('user1')

        self.client.blueprints.update(self.BLUEPRINT_ID, {'creator': 'admin'})
        self.client.users.delete('user1')
        self.client.blueprints.delete(self.BLUEPRINT_ID)

    def test_not_allowed(self):
        self.client.tenants.create('test_tenant')
        self.client.users.create('user1', 'password1', 'default')
        self.client.tenants.add_user('user1', 'test_tenant', 'user')

        a_client = self.create_rest_client(
            username='user1', password='password1', tenant='test_tenant')
        a_client.blueprints.upload(
            resource('dsl/{}'.format(self.BLUEPRINT_FILENAME)),
            entity_id=self.BLUEPRINT_ID)
        with self.assertRaisesRegex(ForbiddenError, 'set_owner'):
            a_client.blueprints.update(self.BLUEPRINT_ID, {'creator': 'admin'})

        a_client.blueprints.delete(self.BLUEPRINT_ID)
        self.client.tenants.remove_user('user1', 'test_tenant')
        self.client.users.delete('user1')
        self.client.tenants.delete('test_tenant')

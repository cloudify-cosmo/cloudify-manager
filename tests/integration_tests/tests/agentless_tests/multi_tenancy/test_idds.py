import pytest

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_premium


class MultiTenantIDDsTest(AgentlessTestCase):
    def setUp(self):
        self.client.tenants.create('alice')
        self.client.tenants.add_user('admin', 'alice', 'manager')
        self.alice_client = self.create_rest_client(
            username='admin',
            password='admin',
            tenant='alice'
        )
        self.client.tenants.create('bob')
        self.client.tenants.add_user('admin', 'bob', 'manager')
        self.bob_client = self.create_rest_client(
            username='admin',
            password='admin',
            tenant='bob'
        )
        self.blueprint_parent = self.client.blueprints.upload(
            resource('dsl/{}'.format('blueprint_parent.yaml')),
            entity_id='parent',
            visibility='global',
        )
        self.blueprint_child = self.client.blueprints.upload(
            resource('dsl/{}'.format('blueprint_child.yaml')),
            entity_id='child',
            visibility='global',
        )

    def test_right_tenant(self):
        self.client.deployments.create('parent', 'parent')
        self.client.executions.start('parent', 'install')

        self.alice_client.deployments.create('parent', 'parent')
        ex = self.alice_client.executions.start('parent', 'install')
        self.wait_for_execution_to_end(ex, client=self.alice_client)
        self.alice_client.deployments.create('child', 'child')
        ex = self.alice_client.executions.start('child', 'install')
        self.wait_for_execution_to_end(ex, client=self.alice_client)
        ex = self.client.executions.start('parent', 'uninstall')
        self.wait_for_execution_to_end(ex)
        self.client.deployments.delete('parent')
        ex = self.alice_client.executions.start('child', 'uninstall')
        self.wait_for_execution_to_end(ex, client=self.alice_client)
        ex = self.alice_client.executions.start('parent', 'uninstall')
        self.wait_for_execution_to_end(ex, client=self.alice_client)
        self.alice_client.deployments.delete('child')
        self.alice_client.deployments.delete('parent')

    def test_global_visibility(self):
        self.client.deployments.create('parent', 'parent',
                                       visibility='global')
        ex = self.client.executions.start('parent', 'install')
        self.wait_for_execution_to_end(ex)
        self.alice_client.deployments.create('child', 'child')
        ex = self.alice_client.executions.start('child', 'install')
        self.wait_for_execution_to_end(ex, client=self.alice_client)
        self.bob_client.deployments.create('child', 'child')
        ex = self.bob_client.executions.start('child', 'install')
        self.wait_for_execution_to_end(ex, client=self.bob_client)

        with self.assertRaises(CloudifyClientError):
            self.client.executions.start('parent', 'uninstall')

        ex = self.alice_client.executions.start('child', 'uninstall')
        self.wait_for_execution_to_end(ex, client=self.alice_client)

        with self.assertRaises(CloudifyClientError):
            self.client.executions.start('parent', 'uninstall')

        ex = self.bob_client.executions.start('child', 'uninstall')
        self.wait_for_execution_to_end(ex, client=self.bob_client)

        ex = self.client.executions.start('parent', 'uninstall')
        self.wait_for_execution_to_end(ex)
        self.alice_client.deployments.delete('child')
        self.client.deployments.delete('parent')

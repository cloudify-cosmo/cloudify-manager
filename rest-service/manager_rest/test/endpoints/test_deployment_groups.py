from cloudify.models_states import VisibilityState
from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.storage import models

from manager_rest.test import base_test


class DeploymentGroupsTestCase(base_test.BaseServerTestCase):
    def test_get_empty(self):
        result = self.client.deployment_groups.list()
        assert len(result) == 0

    def test_add_empty_group(self):
        result = self.client.deployment_groups.list()
        assert len(result) == 0
        result = self.client.deployment_groups.put('group1')
        assert result['id'] == 'group1'

    def test_add_to_group(self):
        self.put_blueprint()
        self.client.deployments.create('blueprint', 'dep1')
        self.client.deployments.create('blueprint', 'dep2')
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )
        assert set(group['deployment_ids']) == {'dep1', 'dep2'}

    def test_overwrite_group(self):
        self.put_blueprint()
        self.client.deployments.create('blueprint', 'dep1')
        self.client.deployments.create('blueprint', 'dep2')
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert group['deployment_ids'] == ['dep1']

        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert group['deployment_ids'] == ['dep1']

    def test_clear_group(self):
        self.put_blueprint()
        self.client.deployments.create('blueprint', 'dep1')
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert group['deployment_ids'] == ['dep1']

        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=[]
        )
        assert group['deployment_ids'] == []

    def test_update_description(self):
        """When deployment_ids is not provided, the group is not cleared"""
        self.put_blueprint()
        self.client.deployments.create('blueprint', 'dep1')
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert group['deployment_ids'] == ['dep1']

        group = self.client.deployment_groups.put(
            'group1',
            description='descr'
        )
        assert group['description'] == 'descr'

    def test_create_with_blueprint(self):
        self.put_blueprint()
        self.client.deployment_groups.put(
            'group1',
            blueprint_id='blueprint',
            default_inputs={'a': 'b'}
        )
        group = self.sm.get(models.DeploymentGroup, 'group1')
        assert group.default_blueprint.id == 'blueprint'
        assert group.default_inputs == {'a': 'b'}

    def test_set_visibility(self):
        self.client.deployment_groups.put(
            'group1',
            visibility=VisibilityState.PRIVATE
        )
        group = self.sm.get(models.DeploymentGroup, 'group1')
        assert group.visibility == VisibilityState.PRIVATE

        self.client.deployment_groups.put(
            'group1',
            visibility=VisibilityState.TENANT
        )
        assert group.visibility == VisibilityState.TENANT

        with self.assertRaisesRegex(
                CloudifyClientError, 'visibility_states') as cm:
            self.client.deployment_groups.put(
                'group1',
                visibility='invalid visibility'
            )
        assert cm.exception.status_code == 409

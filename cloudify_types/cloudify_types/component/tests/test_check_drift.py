from unittest import mock

from cloudify_rest_client.blueprints import Blueprint
from cloudify_rest_client.deployments import Deployment

from cloudify_types.component.operations import check_drift
from cloudify_types.component.tests.base_test_suite import ComponentTestBase


class TestCheckDrift(ComponentTestBase):
    def setUp(self):
        super().setUp()
        self._client_patch = mock.patch(
            'cloudify.manager.get_rest_client',
            return_value=self.cfy_mock_client,
        )
        self._client_patch.start()

    def tearDown(self):
        self._client_patch.stop()
        super().tearDown()

    def test_no_drift(self):
        ctx = self.get_mock_ctx('test', {
            'resource_config': {
                'blueprint': {
                    'id': 'test',
                }
            },
        })
        self.cfy_mock_client.deployments.set_existing_objects([
            Deployment({'id': 'test', 'labels': [], 'blueprint_id': 'test'})
        ])
        self.cfy_mock_client.blueprints.set_existing_objects([
            Blueprint({'id': 'test'})
        ])
        drift = check_drift(ctx=ctx)
        assert not drift

    def test_blueprint_id_drift(self):
        ctx = self.get_mock_ctx('test', {
            'resource_config': {
                'blueprint': {
                    'id': 'test',
                }
            },
        })
        self.cfy_mock_client.deployments.set_existing_objects([
            Deployment({'id': 'test', 'labels': [], 'blueprint_id': 'test2'})
        ])
        self.cfy_mock_client.blueprints.set_existing_objects([
            Blueprint({'id': 'test2'})
        ])
        drift = check_drift(ctx=ctx)
        assert drift == {'blueprint': ['id']}

    def test_blueprint_labels_drift(self):
        ctx = self.get_mock_ctx('test', {
            'resource_config': {
                'blueprint': {
                    'id': 'test',
                    'labels': [{'key': 'a', 'value': 'c'}],
                }
            },
        })
        self.cfy_mock_client.deployments.set_existing_objects([
            Deployment({'id': 'test', 'labels': [], 'blueprint_id': 'test'})
        ])
        self.cfy_mock_client.blueprints.set_existing_objects([
            Blueprint({'id': 'test', 'labels': [{'key': 'a', 'value': 'b'}]})
        ])
        drift = check_drift(ctx=ctx)
        assert drift == {'blueprint': ['labels']}

    def test_deployment_id_drift(self):
        ctx = self.get_mock_ctx('test2', {
            'resource_config': {
                'deployment': {
                    'id': 'test',
                }
            },
        })
        ctx.instance.runtime_properties.update({
            'deployment': {'id': 'test2'}
        })
        self.cfy_mock_client.deployments.set_existing_objects([
            Deployment({'id': 'test2', 'blueprint_id': 'test'}),
        ])
        self.cfy_mock_client.blueprints.set_existing_objects([
            Blueprint({'id': 'test'})
        ])
        drift = check_drift(ctx=ctx)
        assert drift == {'deployment': ['id']}
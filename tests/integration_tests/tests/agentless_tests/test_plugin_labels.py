import pytest

from time import sleep

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_deployments


@pytest.mark.usefixtures('mock_labels_plugin')
class PluginWithBlueprintLabelsTest(AgentlessTestCase):
    def test_blueprint_labels_only_from_plugin(self):
        self.client.blueprints.upload(
            resource('dsl/blueprint_with_plugin_no_labels.yaml'),
            entity_id='bp')
        blueprint = self.client.blueprints.get('bp')
        assert 'blueprint_labels' in blueprint.plan
        assert blueprint.plan['blueprint_labels'] == \
               {
                   'key1': {
                       'values': ['plugin_key1_val1']
                   },
                   'key2': {
                       'values': ['plugin_key2_val1', 'plugin_key2_val2']
                   }
               }
        assert 'labels' in blueprint.plan
        assert blueprint.plan['labels'] == \
               {
                   'key1': {
                       'values': ['plugin_key1_val1']
                   },
                   'key2': {
                       'values': ['plugin_key2_val1', 'plugin_key2_val2']
                   }
               }
        self.client.blueprints.delete('bp')

    def test_blueprint_labels_from_plugin_and_blueprint(self):
        self.client.blueprints.upload(
            resource('dsl/blueprint_with_plugin_and_labels.yaml'),
            entity_id='bp')
        blueprint = self.client.blueprints.get('bp')
        assert 'blueprint_labels' in blueprint.plan
        assert blueprint.plan['blueprint_labels'] == \
               {
                   'key1': {
                       'values': ['plugin_key1_val1']
                   },
                   'key2': {
                       'values': ['bp_key2_val1']
                   }
               }
        assert 'labels' in blueprint.plan
        assert blueprint.plan['labels'] == \
               {
                   'key1': {
                       'values': ['bp_key1_val1']
                   },
                   'key2': {
                       'values': [{'get_input': 'label_value'}]
                   }
               }
        self.client.blueprints.delete('bp')


@pytest.mark.usefixtures('cloudmock_plugin')
class PluginWithoutBlueprintLabelsTest(AgentlessTestCase):
    def test_no_blueprint_labels(self):
        self.client.blueprints.upload(
            resource('dsl/basic.yaml'),
            entity_id='bp')
        blueprint = self.client.blueprints.get('bp')
        assert not blueprint.plan.get('blueprint_labels')
        assert not blueprint.plan.get('labels')

    def test_blueprint_labels(self):
        self.client.blueprints.upload(
            resource('dsl/blueprint_with_labels.yaml'),
            entity_id='bp')
        blueprint = self.client.blueprints.get('bp')
        assert 'blueprint_labels' in blueprint.plan
        assert blueprint.plan['blueprint_labels'] == \
               {
                   'bp_key1': {
                       'values': ['bp_key1_val1']
                   },
                   'bp_key2': {
                       'values': ['bp_key2_val1', 'bp_key2_val2']
                   }
               }
        assert 'labels' in blueprint.plan
        assert blueprint.plan['labels'] == \
               {
                   'key1': {
                       'values': ['key1_val1']
                   },
                   'key2': {
                       'values': ['key2_val1', {'get_input': 'label_value'}]
                   }
               }


@pytest.mark.usefixtures('mock_labels_plugin')
class PluginWithResourceTagsTest(AgentlessTestCase):
    def test_resource_tags_propagation(self):
        self.client.blueprints.upload(
            resource('dsl/blueprint_with_plugin_and_labels.yaml'),
            entity_id='bp')
        blueprint = self.client.blueprints.get('bp')
        assert 'resource_tags' in blueprint.plan
        assert blueprint.plan['resource_tags'] == \
               {
                   'key1': 'value1',
                   'key2': 'value2',
                   'boolean_value': False,
                   'deployment_id': {'get_sys': ['deployment', 'id']},
                   'owner': {'get_sys': ['deployment', 'owner']},
               }

        self.client.deployments.create('bp', 'dep')
        deployment = self.client.deployments.get('dep')
        assert 'resource_tags' in deployment
        assert deployment['resource_tags'] == \
               {
                   'key1': 'value1',
                   'key2': 'value2',
                   'boolean_value': False,
                   'deployment_id': {'get_sys': ['deployment', 'id']},
                   'owner': {'get_sys': ['deployment', 'owner']},
               }

        self.client.deployments.delete('dep')
        self._wait_until_deployment_deleted('dep')
        self.client.blueprints.delete('bp')

    def test_resource_tags_intrinsic_functions(self):
        self.client.blueprints.upload(
            resource('dsl/blueprint_with_resource_tags.yaml'),
            entity_id='bp')
        self.client.deployments.create('bp', 'dep')
        self.execute_workflow('execute_operation',
                              'dep',
                              parameters={'operation': 'test.context'},
                              )

        self.client.deployments.delete('dep')
        self._wait_until_deployment_deleted('dep')
        self.client.blueprints.delete('bp')

    def _wait_until_deployment_deleted(self, deployment_id, timeout_sec=5):
        ticks = timeout_sec * 5
        while ticks > 0:
            try:
                self.client.deployments.get(deployment_id)
            except Exception:
                return
            sleep(0.2)

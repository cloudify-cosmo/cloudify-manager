import pytest

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

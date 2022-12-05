import pytest

from integration_tests import AgentlessTestCase

pytestmark = pytest.mark.group_general


class TestBlueprintParsing(AgentlessTestCase):
    def test_requirements_parent_capabilities(self):
        bp = """
tosca_definitions_version: cloudify_dsl_1_5
imports:
  - cloudify/types/types.yaml
node_types:
    t1:
        derived_from: cloudify.nodes.Root
        properties:
            prop1: {}
node_templates:
    n1:
        type: t1
        properties:
            prop1: {get_environment_capability: cap1}
outputs:
    out1:
        value: {get_environment_capability: [cap2, key1]}
"""
        self.upload_blueprint_resource(
            self.make_yaml_file(bp),
            blueprint_id='bp1',
        )
        bp = self.client.blueprints.get('bp1')
        assert 'requirements' in bp.plan
        requirements = bp.plan['requirements']
        assert 'parent_capabilities' in requirements
        parent_capabilities = requirements['parent_capabilities']
        assert ['cap1'] in parent_capabilities
        assert ['cap2', 'key1'] in parent_capabilities

    def test_requirements_secrets(self):
        bp = """
tosca_definitions_version: cloudify_dsl_1_5
imports:
  - cloudify/types/types.yaml
node_types:
    type:
        properties:
            property_1: {}
node_templates:
    node:
        type: type
        properties:
            property_1: { get_secret: sec1 }
outputs:
    out1:
        value: { get_secret: [sec2, attr] }
    out2:
        value: { get_secret: {get_secret: sec3} }
"""
        self.upload_blueprint_resource(
            self.make_yaml_file(bp),
            blueprint_id='bp1',
        )
        bp = self.client.blueprints.get('bp1')
        assert 'requirements' in bp.plan
        requirements = bp.plan['requirements']
        assert 'secrets' in requirements
        required_secrets = requirements['secrets']
        assert 'sec1' in required_secrets
        assert ['sec2', 'attr'] in required_secrets
        assert 'sec3' in required_secrets
        assert {'get_secret': 'sec3'} in required_secrets

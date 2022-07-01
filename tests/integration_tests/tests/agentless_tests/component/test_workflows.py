from datetime import datetime, timedelta
from time import sleep

import pytest

from integration_tests import AgentlessTestCase

pytestmark = pytest.mark.group_service_composition


COMPONENT_BLUEPRINT = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml

node_templates:
  basic_node:
    type: cloudify.nodes.Component
    properties:
      resource_config:
        blueprint:
          external_resource: true
          id: basic
        deployment:
          id: basic
"""

FAILING_HEAL_COMPONENT_BLUEPRINT = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml
  - plugin:cloudmock

node_types:
  failing_heal_type:
    derived_from: cloudify.nodes.Component
    interfaces:
      cloudify.interfaces.lifecycle:
        heal:
          implementation: cloudmock.cloudmock.tasks.failing

node_templates:
  basic_node:
    type: failing_heal_type
    properties:
      resource_config:
        blueprint:
          external_resource: true
          id: basic
        deployment:
          id: basic
"""


class BasicWorkflowsTest(AgentlessTestCase):
    def setUp(self):
        basic_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml

node_templates:
  root_node:
    type: cloudify.nodes.Root
"""
        self.client.blueprints.upload(
            self.make_yaml_file(basic_blueprint),
            entity_id='basic'
        )

    def test_basic_components_heal(self):
        test_blueprint_path = self.make_yaml_file(COMPONENT_BLUEPRINT)
        deployment, _ = self.deploy_application(test_blueprint_path)
        assert len(self.client.deployments.list()) == 2

        self.client.deployments.delete('basic', force=True)
        _wait_until(lambda: not self.client.deployments.get('basic'))
        assert len(self.client.deployments.list()) == 1

        self.execute_workflow('heal', deployment.id)
        assert len(self.client.deployments.list()) == 2

    def test_nested_components_heal_success(self):
        test_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml

node_templates:
  component_node:
    type: cloudify.nodes.Component
    properties:
      resource_config:
        blueprint:
          external_resource: true
          id: component
        deployment:
          id: component
        """
        self.client.blueprints.upload(
            self.make_yaml_file(COMPONENT_BLUEPRINT),
            entity_id='component'
        )
        test_blueprint_path = self.make_yaml_file(test_blueprint)
        deployment, _ = self.deploy_application(test_blueprint_path)
        assert len(self.client.deployments.list()) == 3

        self.client.deployments.delete('basic', force=True)
        _wait_until(lambda: not self.client.deployments.get('basic'))
        assert len(self.client.deployments.list()) == 2

        self.execute_workflow('heal', deployment.id)
        assert len(self.client.deployments.list()) == 3

    @pytest.mark.usefixtures('cloudmock_plugin')
    def test_nested_components_heal_failure(self):
        test_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml

node_templates:
  component_node:
    type: cloudify.nodes.Component
    properties:
      resource_config:
        blueprint:
          external_resource: true
          id: component
        deployment:
          id: component
"""
        self.client.blueprints.upload(
            self.make_yaml_file(FAILING_HEAL_COMPONENT_BLUEPRINT),
            entity_id='component'
        )
        test_blueprint_path = self.make_yaml_file(test_blueprint)
        deployment, _ = self.deploy_application(test_blueprint_path)
        assert len(self.client.deployments.list()) == 3

        self.client.deployments.delete('basic', force=True)
        _wait_until(lambda: not self.client.deployments.get('basic'))
        assert len(self.client.deployments.list()) == 2

        self.execute_workflow('heal', deployment.id)
        assert len(self.client.deployments.list()) == 3


def _wait_until(fn,
                timeout_seconds=10,
                sleep_seconds=0.2):
    timeout_at = datetime.now() + timedelta(seconds=timeout_seconds)
    while datetime.now() < timeout_at:
        try:
            if fn():
                return
        except Exception:
            pass
        sleep(sleep_seconds)

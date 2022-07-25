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

BASIC_BLUEPRINT = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
- cloudify/types/types.yaml

node_templates:
  root_node:
    type: cloudify.nodes.Root
"""


class BasicWorkflowsTest(AgentlessTestCase):
    def test_basic_components_heal(self):
        self.client.blueprints.upload(
            self.make_yaml_file(BASIC_BLUEPRINT),
            entity_id='basic',
        )
        test_blueprint_path = self.make_yaml_file(COMPONENT_BLUEPRINT)
        deployment, _ = self.deploy_application(test_blueprint_path)
        assert len(self.client.deployments.list()) == 2

        self.client.deployments.delete('basic', force=True)
        _wait_until(lambda: not self.client.deployments.get('basic'))
        assert len(self.client.deployments.list()) == 1

        self.execute_workflow('heal', deployment.id)
        assert len(self.client.deployments.list()) == 2

    def test_nested_components_heal_success(self):
        self.client.blueprints.upload(
            self.make_yaml_file(BASIC_BLUEPRINT),
            entity_id='basic',
        )
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
    def test_heal_failure_reinstall(self):
        # there's a blueprint with a component, and the component is going
        # to fail check_status, and heal - it will have to be reinstalled
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
        component_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml
  - plugin:cloudmock

node_templates:
  root_node:
    type: cloudify.nodes.Root
    interfaces:
      cloudify.interfaces.validation:
        check_status: cloudmock.cloudmock.tasks.maybe_failing
      cloudify.interfaces.lifecycle:
        create: cloudmock.cloudmock.tasks.clear_fail_flag
        heal: cloudmock.cloudmock.tasks.failing
"""
        self.client.blueprints.upload(
            self.make_yaml_file(component_blueprint),
            entity_id='component',
        )
        test_blueprint_path = self.make_yaml_file(test_blueprint)
        deployment, _ = self.deploy_application(test_blueprint_path)
        assert len(self.client.deployments.list()) == 2

        # now, let's update the node-instance inside the component deployment
        # to fail check_status: it will keep failing until reinstalled
        # (because the create operation clears the fail flag, allowing
        # check_status to succeed; but the heal operation always fails)
        ni = self.client.node_instances.list(
            deployment_id='component',
            node_id='root_node',
        ).one()
        self.client.node_instances.update(
            ni.id,
            version=ni.version,
            runtime_properties={'fail': True},
        )
        with self.assertRaises(RuntimeError):
            self.execute_workflow('check_status', 'component')

        self.execute_workflow('heal', deployment.id)
        component_executions = [
            exc.workflow_id
            for exc in self.client.executions.list(deployment_id='component')
        ]
        # there's 2 check_status executions: one we called directly above,
        # and one called by the check_status operation on the Component
        # node in the main deployment
        assert component_executions.count('check_status') == 2

        # there's only 1 heal execution: the one called by the heal operation
        # on the Component node in the main deployment
        assert component_executions.count('heal') == 1

        heal_execution = self.client.executions.list(
            deployment_id='component',
            workflow_id='heal',
        ).one()
        heal_graphs = [
            tg.name for tg in self.client.tasks_graphs.list(heal_execution.id)
        ]
        # check that heal did call exactly the graphs we expected:
        # a check_status first (which failed), then a heal (which also failed),
        # and then a fallback to reinstall
        # NOTE: this assert is VERY tightly coupled to the implementation. If
        # it fails often when changing the heal workflow impl, we can make it
        # more lenient
        assert heal_graphs == [
            'check_status',
            'heal',
            'reinstall-uninstall',
            'reinstall-install',
        ]


class DeploymentUpdateTest(AgentlessTestCase):
    COMP_BLUEPRINT = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml

inputs:
  foo:
    type: integer

node_templates:
  root_node:
    type: cloudify.nodes.Root

capabilities:
  foo:
    value: { get_input: foo }
"""
    PARENT_BLUEPRINT = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml

inputs:
  foo:
    default: 255

node_templates:
  comp_node:
    type: cloudify.nodes.Component
    properties:
      resource_config:
        blueprint:
          external_resource: true
          id: comp
        deployment:
          id: comp
          inputs:
            foo: { get_input: foo }
        """

    def test_components_update_inputs(self):
        self.client.blueprints.upload(
            self.make_yaml_file(DeploymentUpdateTest.COMP_BLUEPRINT),
            entity_id='comp'
        )
        test_blueprint_path = self.make_yaml_file(
            DeploymentUpdateTest.PARENT_BLUEPRINT)
        deployment, _ = self.deploy_application(test_blueprint_path)
        comp_capabilities = self.client.deployments.capabilities.get('comp')
        assert comp_capabilities['capabilities'] == {'foo': 255}

        self.client.deployment_updates.update_with_existing_blueprint(
            deployment.id,
            blueprint_id=deployment.blueprint_id,
            inputs={'foo': 256}
        )
        self.wait_for_all_executions_to_end()

        # Assert that the update was successful
        comp_capabilities = self.client.deployments.capabilities.get('comp')
        assert comp_capabilities['capabilities'] == {'foo': 256}

        # Assert `comp` was updated not re-installed
        comp_workflows = [
            c.workflow_id
            for c in self.client.executions.list(deployment_id='comp')
        ]
        assert 'uninstall' not in comp_workflows
        assert 'update' in comp_workflows

    def test_components_update_blueprint(self):
        new_component_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml

inputs:
  foo:
    description: Another testing input
    type: integer
  bar:
    description: Another testing input
    type: integer

node_templates:
  root_node:
    type: cloudify.nodes.Root

capabilities:
  bar:
    description: Another testing capability
    value: { get_input: bar }
  foo:
    description: Another testing capability
    value: { get_input: foo }
"""
        new_parent_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml

inputs:
  foo:
    description: Another testing input
    type: integer
  bar:
    description: Another testing input
    type: integer

node_templates:
  comp_node:
    type: cloudify.nodes.Component
    properties:
      resource_config:
        blueprint:
          external_resource: true
          id: new_comp
        deployment:
          inputs:
            foo: { get_input: foo }
            bar: { get_input: bar }
        """
        self.client.blueprints.upload(
            self.make_yaml_file(DeploymentUpdateTest.COMP_BLUEPRINT),
            entity_id='comp'
        )
        test_blueprint_path = self.make_yaml_file(
            DeploymentUpdateTest.PARENT_BLUEPRINT)
        deployment, _ = self.deploy_application(test_blueprint_path)
        comp_capabilities = self.client.deployments.capabilities.get('comp')
        assert comp_capabilities['capabilities'] == {'foo': 255}

        self.client.blueprints.upload(
            self.make_yaml_file(new_component_blueprint),
            entity_id='new_comp'
        )
        self.client.blueprints.upload(
            self.make_yaml_file(new_parent_blueprint),
            entity_id='new_parent'
        )
        self.client.deployment_updates.update_with_existing_blueprint(
            deployment.id,
            blueprint_id='new_parent',
            inputs={'foo': 127, 'bar': 511},
        )
        self.wait_for_all_executions_to_end()

        # Assert that the update was successful
        comp = self.client.deployments.get('comp')
        assert comp.blueprint_id == 'new_comp'
        comp_capabilities = self.client.deployments.capabilities.get('comp')
        assert comp_capabilities['capabilities'] == {'foo': 127, 'bar': 511}

    def test_components_update_labels(self):
        new_parent_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml

inputs:
  foo:
    default: 255

node_templates:
  comp_node:
    type: cloudify.nodes.Component
    properties:
      resource_config:
        blueprint:
          external_resource: true
          id: comp
        deployment:
          id: comp
          inputs:
            foo: { get_input: foo }
          labels:
            - lorem: ipsum
        """
        self.client.blueprints.upload(
            self.make_yaml_file(DeploymentUpdateTest.COMP_BLUEPRINT),
            entity_id='comp'
        )
        test_blueprint_path = self.make_yaml_file(
            DeploymentUpdateTest.PARENT_BLUEPRINT)
        deployment, _ = self.deploy_application(test_blueprint_path)
        comp_deployment = self.client.deployments.get('comp')
        assert all(label['key'] == 'csys-obj-parent'
                   for label in comp_deployment.labels)

        self.client.blueprints.upload(
            self.make_yaml_file(new_parent_blueprint),
            entity_id='new_parent'
        )
        self.client.deployment_updates.update_with_existing_blueprint(
            deployment.id,
            blueprint_id='new_parent',
        )
        self.wait_for_all_executions_to_end()

        # Assert that the update was executed, not re-install
        assert 'uninstall' not in [
            c.workflow_id
            for c in self.client.executions.list(deployment_id='comp')
        ]
        # Assert that the update was successful
        comp_deployment = self.client.deployments.get('comp')
        assert any(label['key'] == 'lorem' and label['value'] == 'ipsum'
                   for label in comp_deployment.labels)


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

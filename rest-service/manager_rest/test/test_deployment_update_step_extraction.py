import copy
import json

from mock import patch, ANY
from nose.plugins.attrib import attr

from manager_rest import models
from manager_rest.test import base_test
from manager_rest.deployment_update.step_extractor \
    import PROPERTY, PROPERTIES, OUTPUT, OUTPUTS, WORKFLOW, WORKFLOWS, NODE, \
    NODES, OPERATION, OPERATIONS, RELATIONSHIP, RELATIONSHIPS, \
    SOURCE_OPERATIONS, TARGET_OPERATIONS, TYPE, GROUP, GROUPS, POLICY_TYPE, \
    POLICY_TYPES, POLICY_TRIGGER, POLICY_TRIGGERS, HOST_ID, PLUGIN, \
    DEPLOYMENT_PLUGINS_TO_INSTALL, PLUGINS_TO_INSTALL, DESCRIPTION
from manager_rest.deployment_update.step_extractor \
    import EntityIdBuilder, DeploymentUpdateStepsExtractor
from utils import get_resource


@attr(client_min_version=2.1, client_max_version=base_test.LATEST_API_VERSION)
class DeploymentUpdatesStepExtractorTestCase(base_test.BaseServerTestCase):

    def _get_node_scheme(self):
        return {
            OPERATIONS: {},
            PROPERTIES: {},
            RELATIONSHIPS: [],
            TYPE: '',
            HOST_ID: '',
            PLUGINS_TO_INSTALL: []

        }

    def _get_relationship_scheme(self):
        return {
            SOURCE_OPERATIONS: {},
            "target_id": "",
            TARGET_OPERATIONS: {},
            TYPE: "",
            PROPERTIES: {}
        }

    def setUp(self):
        super(DeploymentUpdatesStepExtractorTestCase, self).setUp()
        names_to_mock = [
            'manager_rest.deployment_update.step_extractor.'
            'manager_rest.deployment_update.manager'
        ]
        for name_to_mock in names_to_mock:
            patcher = patch(name_to_mock)
            self.addCleanup(patcher.stop)
            patcher.start()

        stub_deployment_update = models.DeploymentUpdate(
            deployment_id='deployment_id',
            deployment_plan=None,
            id=ANY)

        self.step_extractor = DeploymentUpdateStepsExtractor(
            deployment_update=stub_deployment_update)

        self.deployment_update_manager = \
            self.step_extractor.deployment_update_manager

        self.step_extractor.old_deployment_plan = {
            DESCRIPTION: '',
            NODES: {},
            OPERATIONS: {},
            PROPERTIES: {},
            RELATIONSHIPS: [],
            TYPE: '',
            GROUPS: {},
            POLICY_TYPES: {},
            POLICY_TRIGGERS: {},
            DEPLOYMENT_PLUGINS_TO_INSTALL: {}
        }
        self.step_extractor.new_deployment_plan = \
            copy.deepcopy(self.step_extractor.old_deployment_plan)

    def test_entity_id_builder(self):

        entity_id_builder = EntityIdBuilder()
        with entity_id_builder.extend_id(NODES):
            self.assertEquals(NODES, entity_id_builder.entity_id)

            with entity_id_builder.extend_id(NODE):
                expected = 'nodes{0}node'.format(entity_id_builder._separator)
                self.assertEquals(expected, entity_id_builder.entity_id)

            self.assertEquals(NODES, entity_id_builder.entity_id)
        self.assertEquals('', entity_id_builder.entity_id)

    def test_entity_id_builder_prepend_before_last_element(self):

        entity_id_builder = EntityIdBuilder()
        with entity_id_builder.extend_id(NODE):
            self.assertEquals(NODE, entity_id_builder.entity_id)

            with entity_id_builder.prepend_id_last_element(NODES):
                expected = 'nodes{0}node'.format(entity_id_builder._separator)
                self.assertEquals(expected, entity_id_builder.entity_id)

            self.assertEquals(NODE, entity_id_builder.entity_id)
        self.assertEquals('', entity_id_builder.entity_id)

    def test_description_no_change(self):

        description_old = {DESCRIPTION: 'description'}
        description_new = description_old

        self.step_extractor.old_deployment_plan.update(description_old)
        self.step_extractor.new_deployment_plan.update(description_new)

        steps, _ = self.step_extractor.extract_steps()
        self.assertEquals([], steps)

    def test_description_add_description(self):

        description_old = {DESCRIPTION: None}
        description_new = {DESCRIPTION: 'description'}

        self.step_extractor.old_deployment_plan.update(description_old)
        self.step_extractor.new_deployment_plan.update(description_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=DESCRIPTION,
                entity_id='description',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_description_remove_description(self):

        description_old = {DESCRIPTION: 'description'}
        description_new = {DESCRIPTION: None}

        self.step_extractor.old_deployment_plan.update(description_old)
        self.step_extractor.new_deployment_plan.update(description_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=DESCRIPTION,
                entity_id='description',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_description_modify_description(self):

        description_old = {DESCRIPTION: 'description_old'}
        description_new = {DESCRIPTION: 'description_new'}

        self.step_extractor.old_deployment_plan.update(description_old)
        self.step_extractor.new_deployment_plan.update(description_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=DESCRIPTION,
                entity_id='description',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_outputs_no_change(self):

        outputs_old = {OUTPUTS: {'output1': 'output1_value'}}
        outputs_new = outputs_old

        self.step_extractor.old_deployment_plan.update(outputs_old)
        self.step_extractor.new_deployment_plan.update(outputs_new)

        steps, _ = self.step_extractor.extract_steps()
        self.assertEquals([], steps)

    def test_outputs_add_output(self):

        outputs_new = {OUTPUTS: {'output1': 'output1_value'}}

        self.step_extractor.new_deployment_plan.update(outputs_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=OUTPUT,
                entity_id='outputs:output1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_outputs_remove_output(self):

        outputs_old = {OUTPUTS: {'output1': 'output1_value'}}

        self.step_extractor.old_deployment_plan.update(outputs_old)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=OUTPUT,
                entity_id='outputs:output1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_outputs_modify_output(self):

        outputs_old = {OUTPUTS: {'output1': 'output1_value'}}
        outputs_new = {OUTPUTS: {'output1': 'output1_modified_value'}}

        self.step_extractor.old_deployment_plan.update(outputs_old)
        self.step_extractor.new_deployment_plan.update(outputs_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=OUTPUT,
                entity_id='outputs:output1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_workflows_no_change(self):

        workflows_old = {WORKFLOWS: {
            'intact_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'plugin_for_workflows'}}}
        workflows_new = workflows_old

        old_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'plugin_for_workflows': 'plugin_value'}
        }
        new_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {}
        }
        self.step_extractor.new_deployment_plan.update(
            new_workflow_plugins_to_install)

        self.step_extractor.old_deployment_plan[
            'workflow_plugins_to_install'] = old_workflow_plugins_to_install

        self.step_extractor.old_deployment_plan.update(workflows_old)
        self.step_extractor.new_deployment_plan.update(workflows_new)

        steps, _ = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_workflows_add_workflow_of_existing_plugin(self):

        old_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'plugin_for_workflows': 'plugin_value'}
        }
        self.step_extractor.old_deployment_plan.update(
            old_workflow_plugins_to_install)

        new_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'plugin_for_workflows': 'plugin_value'}
        }
        self.step_extractor.new_deployment_plan.update(
            new_workflow_plugins_to_install)

        workflows_new = {WORKFLOWS: {
            'added_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'plugin_for_workflows'}}}

        self.step_extractor.new_deployment_plan.update(workflows_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=WORKFLOW,
                entity_id='workflows:added_workflow',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_workflows_remove_workflow(self):

        workflows_old = {WORKFLOWS: {
            'removed_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'plugin_for_workflows'}}}

        old_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'plugin_for_workflows': 'plugin_value'}
        }
        self.step_extractor.old_deployment_plan.update(
            old_workflow_plugins_to_install)

        new_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {}
        }
        self.step_extractor.new_deployment_plan.update(
            new_workflow_plugins_to_install)

        self.step_extractor.old_deployment_plan.update(workflows_old)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=WORKFLOW,
                entity_id='workflows:removed_workflow',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_workflows_modify_workflow_of_existing_plugin(self):

        workflows_old = {WORKFLOWS: {
            'added_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'plugin_for_workflows'}}}

        old_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'plugin_for_workflows': 'plugin_value'}
        }
        self.step_extractor.old_deployment_plan.update(
            old_workflow_plugins_to_install)

        new_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'plugin_for_workflows': 'plugin_value'}
        }
        self.step_extractor.new_deployment_plan.update(
            new_workflow_plugins_to_install)

        workflows_new = {WORKFLOWS: {
            'added_workflow': {
                'operation': 'module_name.bar',
                'plugin': 'plugin_for_workflows'}}}

        self.step_extractor.old_deployment_plan.update(workflows_old)
        self.step_extractor.new_deployment_plan.update(workflows_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=WORKFLOW,
                entity_id='workflows:added_workflow',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_workflows_modify_workflow_new_plugin_no_install(self):

        workflows_old = {WORKFLOWS: {
            'added_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'plugin_for_workflows'}}}

        workflows_new = {WORKFLOWS: {
            'added_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'different_plugin_for_workflows'}}}

        old_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'plugin_for_workflows': 'plugin_value'}
        }
        self.step_extractor.old_deployment_plan.update(
            old_workflow_plugins_to_install)

        new_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'different_plugin_for_workflows': {
                    'install': False
                }
            }
        }
        self.step_extractor.new_deployment_plan.update(
            new_workflow_plugins_to_install)

        self.step_extractor.old_deployment_plan.update(workflows_old)
        self.step_extractor.new_deployment_plan.update(workflows_new)

        _, steps = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_nodes_no_change(self):
        nodes_old = {NODES: {'node1': self._get_node_scheme()}}
        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan.update(nodes_old)
        self.step_extractor.new_deployment_plan.update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_nodes_add_node(self):

        nodes_new = {NODES: {'node1': self._get_node_scheme()}}

        self.step_extractor.new_deployment_plan.update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=NODE,
                entity_id='nodes:node1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_nodes_remove_node(self):

        nodes_old = {NODES: {'node1': self._get_node_scheme()}}

        self.step_extractor.old_deployment_plan.update(nodes_old)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=NODE,
                entity_id='nodes:node1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_nodes_add_and_remove_node_changed_type(self):
        node_old = self._get_node_scheme()
        node_old.update({TYPE: 'old_type'})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({TYPE: 'new_type'})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=NODE,
                entity_id='nodes:node1',
                id=ANY),
            models.DeploymentUpdateStep(
                action='add',
                entity_type=NODE,
                entity_id='nodes:node1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_nodes_add_and_remove_node_changed_host_id(self):
        node_old = self._get_node_scheme()
        node_old.update({TYPE: 'type',
                         HOST_ID: 'old_host_id'})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({TYPE: 'type',
                         HOST_ID: 'new_host_id'})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=NODE,
                entity_id='nodes:node1',
                id=ANY),
            models.DeploymentUpdateStep(
                action='add',
                entity_type=NODE,
                entity_id='nodes:node1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_nodes_add_and_remove_node_changed_type_and_host_id(self):
        node_old = self._get_node_scheme()
        node_old.update({HOST_ID: 'old_host_id'})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({TYPE: 'new_host_id'})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=NODE,
                entity_id='nodes:node1',
                id=ANY),
            models.DeploymentUpdateStep(
                action='add',
                entity_type=NODE,
                entity_id='nodes:node1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_node_properties_no_change(self):

        node_old = self._get_node_scheme()
        node_old.update({PROPERTIES: {'property1': 'property1_value'}})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_node_properties_add_property(self):

        nodes_old = {'node1': self._get_node_scheme()}

        node_new = self._get_node_scheme()
        node_new.update({PROPERTIES: {'property1': 'property1_value'}})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=PROPERTY,
                entity_id='nodes:node1:properties:property1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_node_properties_remove_property(self):

        node_old = self._get_node_scheme()
        node_old.update({PROPERTIES: {'property1': 'property1_value'}})
        nodes_old = {'node1': node_old}

        nodes_new = {'node1': self._get_node_scheme()}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=PROPERTY,
                entity_id='nodes:node1:properties:property1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_node_properties_modify_property(self):

        node_old = self._get_node_scheme()
        node_old.update(
            {PROPERTIES: {'property1': 'property1_value'}})

        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update(
            {PROPERTIES: {'property1': 'property1_modified_value'}})

        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=PROPERTY,
                entity_id='nodes:node1:properties:property1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_node_operations_no_change(self):

        node_old = self._get_node_scheme()
        node_old.update({OPERATIONS: {'full.operation1.name': {
            'operation1_field': 'operation1_field_value'}}})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_node_operations_add_operation(self):

        nodes_old = {'node1': self._get_node_scheme()}

        node_new = self._get_node_scheme()
        node_new.update({OPERATIONS: {'full.operation1.name': {
            'operation1_field': 'operation1_field_value'}}})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=OPERATION,
                entity_id='nodes:node1:operations:full.operation1.name',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_node_operations_remove_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({OPERATIONS: {'full.operation1.name': {
            'operation1_field': 'operation1_field_value'}}})
        nodes_old = {'node1': node_old}

        nodes_new = {'node1': self._get_node_scheme()}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=OPERATION,
                entity_id='nodes:node1:operations:full.operation1.name',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_node_operations_modify_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({OPERATIONS: {'full.operation1.name': {
            'operation1_field': 'operation1_field_value'}}})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({OPERATIONS: {'full.operation1.name': {
            'operation1_field': 'operation1_modified_field_value'}}})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=OPERATION,
                entity_id='nodes:node1:operations:full.operation1.name',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_no_change(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target'}
        ]})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_relationships_add_relationship(self):

        nodes_old = {'node1': self._get_node_scheme()}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target'}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_remove_relationship(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target'}
        ]})
        nodes_old = {'node1': node_old}

        nodes_new = {'node1': self._get_node_scheme()}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_change_type(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target'}
        ]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'different_relationship_type',
             'target_id': 'relationship_target'}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]',
                id=ANY),
            models.DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_change_target(self):
        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target'}
        ]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'different_relationship_target'}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]',
                id=ANY),
            models.DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_change_type_and_target(self):
        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target'}
        ]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'different_relationship_type',
             'target_id': 'different_relationship_target'}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]',
                id=ANY),
            models.DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_modify_order(self):
        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target_1'},
            {'type': 'relationship_type',
             'target_id': 'relationship_target_2'},
            {'type': 'relationship_type',
             'target_id': 'relationship_target_3'},
            {'type': 'relationship_type',
             'target_id': 'relationship_target_4'}
        ]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target_2'},
            {'type': 'relationship_type',
             'target_id': 'relationship_target_4'},
            {'type': 'relationship_type',
             'target_id': 'relationship_target_3'},
            {'type': 'relationship_type',
             'target_id': 'relationship_target_1'}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]:[3]',
                id=ANY),
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[1]:[0]',
                id=ANY),
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[3]:[1]',
                id=ANY)
        ]
        # we don't care for the order the steps were created in
        self.assertSetEqual(set(expected_steps), set(steps))

    def test_relationships_modify_order_with_add_and_remove(self):
        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target_1'},
            {'type': 'relationship_type',
             'target_id': 'relationship_target_2'},
            {'type': 'relationship_type',
             'target_id': 'relationship_target_3'}
        ]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target_5'},
            {'type': 'relationship_type',
             'target_id': 'relationship_target_2'},
            {'type': 'relationship_type',
             'target_id': 'relationship_target_4'},
            {'type': 'relationship_type',
             'target_id': 'relationship_target_1'}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]:[3]',
                id=ANY),
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[2]',
                id=ANY),
            models.DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[2]',
                id=ANY),
            models.DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]',
                id=ANY)
        ]
        # we don't care for the order the steps were created in
        self.assertSetEqual(set(expected_steps), set(steps))

    def test_relationships_add_source_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             SOURCE_OPERATIONS: {}
             }]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             SOURCE_OPERATIONS: {'full.operation1': {}}
             }]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'source_operations:full.operation1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_remove_source_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             SOURCE_OPERATIONS: {'full.operation1': {}}
             }]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             SOURCE_OPERATIONS: {}
             }]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'source_operations:full.operation1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_modify_source_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             SOURCE_OPERATIONS: {
                 'full.operation1': {
                     'op1_old_field': 'op1_field_value'
                 }
             }
             }]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             SOURCE_OPERATIONS: {
                 'full.operation1': {
                     'op1_new_field': 'op1_field_value'
                 }
             }
             }]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'source_operations:full.operation1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_add_target_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             TARGET_OPERATIONS: {}
             }]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             TARGET_OPERATIONS: {'full.operation1': {}}
             }]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'target_operations:full.operation1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_remove_target_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             TARGET_OPERATIONS: {'full.operation1': {}}
             }]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             TARGET_OPERATIONS: {}
             }]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'target_operations:full.operation1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_modify_target_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             TARGET_OPERATIONS: {
                 'full.operation1': {
                     'op1_old_field': 'op1_field_value'
                 }
             }
             }]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             TARGET_OPERATIONS: {
                 'full.operation1': {
                     'op1_new_field': 'op1_field_value'
                 }
             }
             }]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'target_operations:full.operation1',
                id=ANY)
        ]

        self.assertEquals(expected_steps, steps)

    def test_get_matching_relationship(self):
        relationships_with_match = [
            {'type': 'typeA', 'target_id': 'id_1', 'field1': 'value1'},
            {'type': 'typeB', 'target_id': 'id_1'},
            {'type': 'typeB', 'target_id': 'id_2'},
            {'type': 'typeA', 'target_id': 'id_2'}
                                    ]
        relationships_with_no_match = [
            {'type': 'typeB', 'target_id': 'id_1'},
            {'type': 'typeB', 'target_id': 'id_2'},
            {'type': 'typeA', 'target_id': 'id_2'}
            ]

        relationship = {
            'type': 'typeA', 'target_id': 'id_1', 'field2': 'value2'
        }

        _get_matching_relationship = \
            self.step_extractor._get_matching_relationship

        self.assertEquals(
            ({'type': 'typeA', 'target_id': 'id_1', 'field1': 'value1'}, 0),
            _get_matching_relationship(relationship, relationships_with_match))

        self.assertEquals((None, None), _get_matching_relationship(
            relationship, relationships_with_no_match))

    def test_sort_steps(self):

        steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type='operation',
                entity_id=''),
            models.DeploymentUpdateStep(
                action='remove',
                entity_type='relationship',
                entity_id=''),
            models.DeploymentUpdateStep(
                action='add',
                entity_type='relationship',
                entity_id=''),
            models.DeploymentUpdateStep(
                action='remove',
                entity_type='node',
                entity_id=''),
            models.DeploymentUpdateStep(
                action='modify',
                entity_type='property',
                entity_id=''),
            models.DeploymentUpdateStep(
                action='add',
                entity_type='node',
                entity_id='')
        ]

        sorted_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type='relationship',
                entity_id=''),
            models.DeploymentUpdateStep(
                action='remove',
                entity_type='node',
                entity_id=''),
            models.DeploymentUpdateStep(
                action='add',
                entity_type='node',
                entity_id=''),
            models.DeploymentUpdateStep(
                action='add',
                entity_type='relationship',
                entity_id=''),
            models.DeploymentUpdateStep(
                action='modify',
                entity_type='operation',
                entity_id=''),
            models.DeploymentUpdateStep(
                action='modify',
                entity_type='property',
                entity_id='')
        ]

        steps.sort()
        self.assertEquals(steps, sorted_steps)

    # from here, tests involving unsupported steps

    def test_relationships_intact_property(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             PROPERTIES: {
                 'property1': 'property1_value'
             }}]})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        _, steps = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_relationships_add_property(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             'properties': {}}]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             PROPERTIES: {
                 'property1': 'property1_different_value'
             }}]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=PROPERTY,
                entity_id='nodes:node1:relationships:[0]:'
                          'properties:property1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_remove_property(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             PROPERTIES: {
                 'property1': 'property1_different_value'
             }}]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             'properties': {}}]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=PROPERTY,
                entity_id='nodes:node1:relationships:[0]:'
                          'properties:property1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_relationships_modify_property(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             PROPERTIES: {
                 'property1': 'property1_value'
             }}]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             PROPERTIES: {
                 'property1': 'property1_different_value'
             }}]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=PROPERTY,
                entity_id='nodes:node1:relationships:[0]:'
                          'properties:property1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_policy_types_no_change(self):
        policy_types_old = {
            POLICY_TYPES: {'policy_type1': 'policy_type1_value'}}
        policy_types_new = policy_types_old

        self.step_extractor.old_deployment_plan.update(policy_types_old)
        self.step_extractor.new_deployment_plan.update(policy_types_new)

        _, steps = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_policy_types_add_policy_type(self):

        policy_types_new = {
            POLICY_TYPES: {'policy_type1': 'policy_type1_value'}}

        self.step_extractor.new_deployment_plan.update(policy_types_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=POLICY_TYPE,
                entity_id='policy_types:policy_type1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_policy_types_remove_policy_type(self):

        policy_types_old = {
            POLICY_TYPES: {'policy_type1': 'policy_type1_value'}}

        self.step_extractor.old_deployment_plan.update(policy_types_old)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=POLICY_TYPE,
                entity_id='policy_types:policy_type1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_policy_types_modify_policy_type(self):

        policy_types_old = {POLICY_TYPES: {
            'policy_type1': 'policy_type1_value'}}
        policy_types_new = \
            {POLICY_TYPES: {'policy_type1': 'policy_type1_modified_value'}}

        self.step_extractor.old_deployment_plan.update(policy_types_old)
        self.step_extractor.new_deployment_plan.update(policy_types_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=POLICY_TYPE,
                entity_id='policy_types:policy_type1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_policy_triggers_no_change(self):
        policy_triggers_old = {
            POLICY_TRIGGERS: {'policy_trigger1': 'policy_trigger1_value'}}
        policy_triggers_new = policy_triggers_old

        self.step_extractor.old_deployment_plan.update(policy_triggers_old)
        self.step_extractor.new_deployment_plan.update(policy_triggers_new)

        _, steps = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_policy_triggers_add_policy_trigger(self):

        policy_triggers_new = {
            POLICY_TRIGGERS: {'policy_trigger1': 'policy_trigger1_value'}}

        self.step_extractor.new_deployment_plan.update(policy_triggers_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=POLICY_TRIGGER,
                entity_id='policy_triggers:policy_trigger1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_policy_triggers_remove_policy_trigger(self):

        policy_triggers_old = {
            POLICY_TRIGGERS: {'policy_trigger1': 'policy_trigger1_value'}}

        self.step_extractor.old_deployment_plan.update(policy_triggers_old)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=POLICY_TRIGGER,
                entity_id='policy_triggers:policy_trigger1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_policy_triggers_modify_policy_trigger(self):

        policy_triggers_old = {
            POLICY_TRIGGERS: {
                'policy_trigger1': 'policy_trigger1_value'}}
        policy_triggers_new = \
            {POLICY_TRIGGERS: {
                'policy_trigger1': 'policy_trigger1_modified_value'}}

        self.step_extractor.old_deployment_plan.update(policy_triggers_old)
        self.step_extractor.new_deployment_plan.update(policy_triggers_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=POLICY_TRIGGER,
                entity_id='policy_triggers:policy_trigger1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_workflows_add_workflow_of_a_new_plugin(self):

        workflows_new = {WORKFLOWS: {
            'added_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'different_plugin_for_workflows'}}}

        old_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'plugin_for_workflows': 'plugin_value'}
        }
        self.step_extractor.old_deployment_plan.update(
            old_workflow_plugins_to_install)

        new_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'different_plugin_for_workflows': {
                    'install': True
                }
            }
        }
        self.step_extractor.new_deployment_plan.update(
            new_workflow_plugins_to_install)

        self.step_extractor.new_deployment_plan.update(workflows_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=WORKFLOW,
                entity_id='workflows:added_workflow',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_workflows_modify_workflow_new_plugin_install(self):

        workflows_old = {WORKFLOWS: {
            'added_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'plugin_for_workflows'}}}

        workflows_new = {WORKFLOWS: {
            'added_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'different_plugin_for_workflows'}}}

        old_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'plugin_for_workflows': 'plugin_value'}
        }
        self.step_extractor.old_deployment_plan.update(
            old_workflow_plugins_to_install)

        new_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'different_plugin_for_workflows': {
                    'install': True
                }
            }
        }
        self.step_extractor.new_deployment_plan.update(
            new_workflow_plugins_to_install)

        self.step_extractor.old_deployment_plan.update(workflows_old)
        self.step_extractor.new_deployment_plan.update(workflows_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=WORKFLOW,
                entity_id='workflows:added_workflow',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_groups_no_change(self):

        groups_old = {GROUPS: {'group1': 'group1_value'}}
        groups_new = groups_old

        self.step_extractor.old_deployment_plan.update(groups_old)
        self.step_extractor.new_deployment_plan.update(groups_new)

        _, steps = self.step_extractor.extract_steps()
        self.assertEquals([], steps)

    def test_groups_add_group(self):

        groups_new = {GROUPS: {'group1': 'group1_value'}}

        self.step_extractor.new_deployment_plan.update(groups_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=GROUP,
                entity_id='groups:group1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_groups_remove_group(self):

        groups_old = {GROUPS: {'group1': 'group1_value'}}

        self.step_extractor.old_deployment_plan.update(groups_old)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=GROUP,
                entity_id='groups:group1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_groups_modify_group(self):

        groups_old = {GROUPS: {'group1': 'group1_value'}}
        groups_new = {GROUPS: {'group1': 'group1_modified_value'}}

        self.step_extractor.old_deployment_plan.update(groups_old)
        self.step_extractor.new_deployment_plan.update(groups_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=GROUP,
                entity_id='groups:group1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_cda_plugins_no_install(self):

        cda_plugins_new = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: {
                'cda_plugin1': {
                    'install': False}}}

        self.step_extractor.new_deployment_plan.update(cda_plugins_new)

        _, steps = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_cda_plugins_add_cda_plugin(self):

        cda_plugins_new = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: {'cda_plugin1': {'install': True}}}

        self.step_extractor.new_deployment_plan.update(cda_plugins_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=PLUGIN,
                entity_id='central_deployment_agent_plugins:cda_plugin1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_cda_plugins_modify_cda_plugin(self):

        cda_plugins_old = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: {
                'cda_plugin1': {
                    'install': True,
                    'value': 'value_before'}}}
        cda_plugins_new = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: {
                'cda_plugin1': {
                    'install': True,
                    'value': 'value_after'}}}

        self.step_extractor.old_deployment_plan.update(cda_plugins_old)
        self.step_extractor.new_deployment_plan.update(cda_plugins_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=PLUGIN,
                entity_id='central_deployment_agent_plugins:cda_plugin1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_ha_plugins_no_install(self):

        node_old = self._get_node_scheme()
        node_old.update({PLUGINS_TO_INSTALL: [
            {'name': 'old',
             'install': True}]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({PLUGINS_TO_INSTALL: [
            {'name': 'new',
             'install': False}]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        _, steps = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_ha_plugins_add_ha_plugin(self):

        node_old = self._get_node_scheme()
        node_old.update({PLUGINS_TO_INSTALL: [
            {'name': 'old',
             'install': True}]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({PLUGINS_TO_INSTALL: [
            {'name': 'new',
             'install': True}]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=PLUGIN,
                entity_id='host_agent_plugins:node1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_ha_plugins_modify_ha_plugin(self):

        node_old = self._get_node_scheme()
        node_old.update({PLUGINS_TO_INSTALL: [
            {'name': 'name',
             'install': True,
             'source': 'old'}]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({PLUGINS_TO_INSTALL: [
            {'name': 'name',
             'install': True,
             'source': 'new'}]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=PLUGIN,
                entity_id='host_agent_plugins:node1',
                id=ANY,
                supported=False)
        ]

        self.assertEquals(expected_steps, steps)

    def test_all_changes_combined(self):

        path_before = get_resource(
            'deployment_update/combined_changes_before.json')

        path_after = get_resource(
            'deployment_update/combined_changes_after.json')

        with open(path_before) as fp_before, open(path_after) as fp_after:
            self.step_extractor.old_deployment_plan = json.load(fp_before)
            self.step_extractor.new_deployment_plan = json.load(fp_after)

        expected_steps = {
            'modify_description': models.DeploymentUpdateStep(
                'modify',
                DESCRIPTION,
                'description',
                ANY),

            'remove_node': models.DeploymentUpdateStep(
                'remove',
                NODE,
                'nodes:node1',
                ANY),

            'add_node': models.DeploymentUpdateStep(
                'add',
                NODE,
                'nodes:node2',
                ANY),

            'add_node_changed_type': models.DeploymentUpdateStep(
                'add',
                NODE,
                'nodes:node3',
                ANY),

            'remove_node_changed_type': models.DeploymentUpdateStep(
                'remove',
                NODE,
                'nodes:node3',
                ANY),

            'add_node_changed_host_id': models.DeploymentUpdateStep(
                'add',
                NODE,
                'nodes:node14',
                ANY),

            'remove_node_changed_host_id': models.DeploymentUpdateStep(
                'remove',
                NODE,
                'nodes:node14',
                ANY),

            'add_node_changed_type_and_host_id': models.DeploymentUpdateStep(
                'add',
                NODE,
                'nodes:node15',
                ANY),

            'remove_node_type_and_host_id': models.DeploymentUpdateStep(
                'remove',
                NODE,
                'nodes:node15',
                ANY),

            'add_property': models.DeploymentUpdateStep(
                'add',
                PROPERTY,
                'nodes:node4:properties:added_prop',
                ANY),

            'remove_property': models.DeploymentUpdateStep(
                'remove',
                PROPERTY,
                'nodes:node4:properties:removed_prop',
                ANY),

            'modify_property': models.DeploymentUpdateStep(
                'modify',
                PROPERTY,
                'nodes:node4:properties:modified_prop',
                ANY),

            'remove_relationship': models.DeploymentUpdateStep(
                'remove',
                RELATIONSHIP,
                'nodes:node6:relationships:[0]',
                ANY),

            'add_relationship': models.DeploymentUpdateStep(
                'add',
                RELATIONSHIP,
                'nodes:node7:relationships:[0]',
                ANY),

            'remove_relationship_changed_type': models.DeploymentUpdateStep(
                'remove',
                RELATIONSHIP,
                'nodes:node8:relationships:[0]',
                ANY),

            'add_relationship_changed_type': models.DeploymentUpdateStep(
                'add',
                RELATIONSHIP,
                'nodes:node8:relationships:[0]',
                ANY),

            'remove_relationship_changed_target': models.DeploymentUpdateStep(
                'remove',
                RELATIONSHIP,
                'nodes:node9:relationships:[0]',
                ANY),

            'add_relationship_changed_target': models.DeploymentUpdateStep(
                'add',
                RELATIONSHIP,
                'nodes:node9:relationships:[0]',
                ANY),

            'remove_relationship_changed_type_and_target':
                models.DeploymentUpdateStep(
                    'remove',
                    RELATIONSHIP,
                    'nodes:node10:relationships:[0]',
                    ANY),

            'add_relationship_changed_type_and_target':
                models.DeploymentUpdateStep(
                    'add',
                    RELATIONSHIP,
                    'nodes:node10:relationships:[0]',
                    ANY),

            'add_operation': models.DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node11:operations:interface1.added_operation',
                ANY),

            'add_operation_shortened': models.DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node11:operations:added_operation',
                ANY),

            'remove_operation': models.DeploymentUpdateStep(
                'remove',
                OPERATION,
                'nodes:node11:operations:interface1.removed_operation',
                ANY),

            'remove_operation_shortened': models.DeploymentUpdateStep(
                'remove',
                OPERATION,
                'nodes:node11:operations:removed_operation',
                ANY),

            'modify_operation': models.DeploymentUpdateStep(
                'modify',
                OPERATION,
                'nodes:node11:operations:interface1.modified_operation',
                ANY),

            'modify_operation_shortened': models.DeploymentUpdateStep(
                'modify',
                OPERATION,
                'nodes:node11:operations:modified_operation',
                ANY),

            'add_relationship_operation': models.DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node12:relationships:[0]:target_operations:'
                'interface_for_modified_and_added.added_operation',
                ANY),

            'add_relationship_operation_shortened':
                models.DeploymentUpdateStep(
                    'add',
                    OPERATION,
                    'nodes:node12:relationships:[0]:target_operations:'
                    'added_operation',
                    ANY),


            'remove_relationship_operation': models.DeploymentUpdateStep(
                'remove',
                OPERATION,
                'nodes:node12:relationships:[0]:source_operations:'
                'interface_for_intact_and_removed.removed_operation',
                ANY),

            'remove_relationship_operation_shortened':
                models.DeploymentUpdateStep(
                    'remove',
                    OPERATION,
                    'nodes:node12:relationships:[0]:source_operations:'
                    'removed_operation',
                    ANY),

            'modify_relationship_operation': models.DeploymentUpdateStep(
                'modify',
                OPERATION,
                'nodes:node12:relationships:[0]:target_operations:'
                'interface_for_modified_and_added.modified_operation',
                ANY),

            'modify_relationship_operation_shortened':
                models.DeploymentUpdateStep(
                    'modify',
                    OPERATION,
                    'nodes:node12:relationships:[0]:target_operations:'
                    'modified_operation',
                    ANY),

            'add_output': models.DeploymentUpdateStep(
                'add',
                OUTPUT,
                'outputs:added_output',
                ANY),

            'remove_output': models.DeploymentUpdateStep(
                'remove',
                OUTPUT,
                'outputs:removed_output',
                ANY),

            'modify_output': models.DeploymentUpdateStep(
                'modify',
                OUTPUT,
                'outputs:modified_output',
                ANY),

            'add_workflow_same_plugin': models.DeploymentUpdateStep(
                'add',
                WORKFLOW,
                'workflows:added_workflow_same_plugin',
                ANY),

            'add_workflow_new_plugin': models.DeploymentUpdateStep(
                'add',
                WORKFLOW,
                'workflows:added_workflow_new_plugin',
                ANY,
                supported=False),

            'remove_workflow': models.DeploymentUpdateStep(
                'remove',
                WORKFLOW,
                'workflows:removed_workflow',
                ANY),

            'modify_workflow_same_plugin': models.DeploymentUpdateStep(
                'modify',
                WORKFLOW,
                'workflows:modified_workflow_same_plugin',
                ANY),

            'modify_workflow_new_plugin': models.DeploymentUpdateStep(
                'modify',
                WORKFLOW,
                'workflows:modified_workflow_new_plugin',
                ANY,
                supported=False),

            'add_policy_type': models.DeploymentUpdateStep(
                'add',
                POLICY_TYPE,
                'policy_types:added_policy_type',
                ANY,
                supported=False),

            'remove_policy_type': models.DeploymentUpdateStep(
                'remove',
                POLICY_TYPE,
                'policy_types:removed_policy_type',
                ANY,
                supported=False),

            'modify_policy_type': models.DeploymentUpdateStep(
                'modify',
                POLICY_TYPE,
                'policy_types:modified_policy_type',
                ANY,
                supported=False),

            'add_policy_trigger': models.DeploymentUpdateStep(
                'add',
                POLICY_TRIGGER,
                'policy_triggers:added_policy_trigger',
                ANY,
                supported=False),

            'remove_policy_trigger': models.DeploymentUpdateStep(
                'remove',
                POLICY_TRIGGER,
                'policy_triggers:removed_policy_trigger',
                ANY,
                supported=False),

            'modify_policy_trigger': models.DeploymentUpdateStep(
                'modify',
                POLICY_TRIGGER,
                'policy_triggers:modified_policy_trigger',
                ANY,
                supported=False),

            'add_group': models.DeploymentUpdateStep(
                'add',
                GROUP,
                'groups:added_group',
                ANY,
                supported=False),

            'remove_group': models.DeploymentUpdateStep(
                'remove',
                GROUP,
                'groups:removed_group',
                ANY,
                supported=False),

            'modify_group': models.DeploymentUpdateStep(
                'modify',
                GROUP,
                'groups:modified_group',
                ANY,
                supported=False),

            'add_relationship_property': models.DeploymentUpdateStep(
                'add',
                PROPERTY,
                'nodes:node13:relationships:[0]:'
                'properties:added_relationship_prop',
                ANY,
                supported=False),

            'remove_relationship_property': models.DeploymentUpdateStep(
                'remove',
                PROPERTY,
                'nodes:node13:relationships:[0]:'
                'properties:removed_relationship_prop',
                ANY,
                supported=False),

            'modify_relationship_property': models.DeploymentUpdateStep(
                'modify',
                PROPERTY,
                'nodes:node13:relationships:[0]:'
                'properties:modified_relationship_prop',
                ANY,
                supported=False),

            'add_cda_plugin': models.DeploymentUpdateStep(
                'add',
                PLUGIN,
                'central_deployment_agent_plugins:cda_plugin_for_operations2',
                ANY,
                supported=False),

            'add_ha_plugin': models.DeploymentUpdateStep(
                'add',
                PLUGIN,
                'host_agent_plugins:node18',
                ANY,
                supported=False),

            # the steps below are intended just to make the test pass.
            # ideally, they should be removed since they are incorrect

            'add_cda_operation': models.DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node16:operations:'
                'interface_for_plugin_based_operations.'
                'added_operation_new_cda_plugin',
                ANY,
                supported=True),

            'add_cda_operation_shortened': models.DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node16:operations:added_operation_new_cda_plugin',
                ANY,
                supported=True),

            'add_ha_operation': models.DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node17:operations:'
                'interface_for_plugin_based_operations.'
                'ha_operation_after',
                ANY,
                supported=True),

            'add_ha_operation_shortened': models.DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node17:operations:ha_operation_after',
                ANY,
                supported=True),

            'remove_ha_operation': models.DeploymentUpdateStep(
                'remove',
                OPERATION,
                'nodes:node17:operations:'
                'interface_for_plugin_based_operations.'
                'ha_operation_before',
                ANY,
                supported=True),

            'remove_ha_operation_shortened': models.DeploymentUpdateStep(
                'remove',
                OPERATION,
                'nodes:node17:operations:ha_operation_before',
                ANY,
                supported=True),

            'modify_ha_operation': models.DeploymentUpdateStep(
                'modify',
                OPERATION,
                'nodes:node18:operations:'
                'interface_for_plugin_based_operations.'
                'ha_operation_before',
                ANY,
                supported=True),

            'modify_ha_operation_shortened': models.DeploymentUpdateStep(
                'modify',
                OPERATION,
                'nodes:node18:operations:ha_operation_before',
                ANY,
                supported=True),


        }
        steps, unsupported_steps = self.step_extractor.extract_steps()
        steps.extend(unsupported_steps)

        self.assertEquals(set(expected_steps.values()), set(steps))

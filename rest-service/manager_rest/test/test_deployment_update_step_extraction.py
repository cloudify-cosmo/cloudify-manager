import copy
import json

from mock import patch, ANY
from nose.plugins.attrib import attr

from manager_rest import models
from manager_rest.test import base_test
from manager_rest.deployment_update.step_extractor \
    import PROPERTY, PROPERTIES, OUTPUT, OUTPUTS, WORKFLOW, WORKFLOWS, NODE, \
    NODES, OPERATION, OPERATIONS, RELATIONSHIP, RELATIONSHIPS, \
    SOURCE_OPERATIONS, TARGET_OPERATIONS, TYPE
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
            TYPE: ''
        }

    def _get_relationship_scheme(self):
        return {
            "source_operations": {},
            "target_id": "",
            "target_operations": {},
            "type": ""
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
            NODES: {},
            OPERATIONS: {},
            PROPERTIES: {},
            RELATIONSHIPS: [],
            TYPE: ''
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

    def test_extract_steps_from_outputs_no_change(self):

        outputs_old = {OUTPUTS: {'output1': 'output1_value'}}
        outputs_new = outputs_old

        self.step_extractor.old_deployment_plan.update(outputs_old)
        self.step_extractor.new_deployment_plan.update(outputs_new)

        steps = self.step_extractor.extract_steps()
        self.assertEquals([], steps)

    def test_extract_steps_from_outputs_add_output(self):

        outputs_new = {OUTPUTS: {'output1': 'output1_value'}}

        self.step_extractor.new_deployment_plan.update(outputs_new)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=OUTPUT,
                entity_id='outputs:output1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_outputs_remove_output(self):

        outputs_old = {OUTPUTS: {'output1': 'output1_value'}}

        self.step_extractor.old_deployment_plan.update(outputs_old)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=OUTPUT,
                entity_id='outputs:output1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_outputs_modify_output(self):

        outputs_old = {OUTPUTS: {'output1': 'output1_value'}}
        outputs_new = {OUTPUTS: {'output1': 'output1_modified_value'}}

        self.step_extractor.old_deployment_plan.update(outputs_old)
        self.step_extractor.new_deployment_plan.update(outputs_new)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=OUTPUT,
                entity_id='outputs:output1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_workflows_no_change(self):

        workflows_old = {WORKFLOWS: {'workflow1': 'workflow1_value'}}
        workflows_new = workflows_old

        self.step_extractor.old_deployment_plan.update(workflows_old)
        self.step_extractor.new_deployment_plan.update(workflows_new)

        steps = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_extract_steps_from_workflows_add_workflow(self):

        workflows_new = {WORKFLOWS: {'workflow1': 'workflow1_value'}}

        self.step_extractor.new_deployment_plan.update(workflows_new)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=WORKFLOW,
                entity_id='workflows:workflow1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_workflows_remove_workflow(self):

        workflows_old = {WORKFLOWS: {'workflow1': 'workflow1_value'}}

        self.step_extractor.old_deployment_plan.update(workflows_old)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=WORKFLOW,
                entity_id='workflows:workflow1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_workflows_modify_workflow(self):

        workflows_old = {WORKFLOWS: {'workflow1': 'workflow1_value'}}
        workflows_new = \
            {WORKFLOWS: {'workflow1': 'workflow1_modified_value'}}

        self.step_extractor.old_deployment_plan.update(workflows_old)
        self.step_extractor.new_deployment_plan.update(workflows_new)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=WORKFLOW,
                entity_id='workflows:workflow1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_nodes_no_change(self):
        nodes_old = {NODES: {'node1': self._get_node_scheme()}}
        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan.update(nodes_old)
        self.step_extractor.new_deployment_plan.update(nodes_new)

        steps = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_extract_steps_from_nodes_add_node(self):

        nodes_new = {NODES: {'node1': self._get_node_scheme()}}

        self.step_extractor.new_deployment_plan.update(nodes_new)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=NODE,
                entity_id='nodes:node1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_nodes_remove_node(self):

        nodes_old = {NODES: {'node1': self._get_node_scheme()}}

        self.step_extractor.old_deployment_plan.update(nodes_old)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=NODE,
                entity_id='nodes:node1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_nodes_add_and_remove_node_changed_type(self):
        node_old = self._get_node_scheme()
        node_old.update({TYPE: 'old_type'})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({TYPE: 'new_type'})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=NODE,
                entity_id='nodes:node1'),
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=NODE,
                entity_id='nodes:node1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_node_properties_no_change(self):

        node_old = self._get_node_scheme()
        node_old.update({PROPERTIES: {'property1': 'property1_value'}})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_extract_steps_from_node_properties_add_property(self):

        nodes_old = {'node1': self._get_node_scheme()}

        node_new = self._get_node_scheme()
        node_new.update({PROPERTIES: {'property1': 'property1_value'}})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=PROPERTY,
                entity_id='nodes:node1:properties:property1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_node_properties_remove_property(self):

        node_old = self._get_node_scheme()
        node_old.update({PROPERTIES: {'property1': 'property1_value'}})
        nodes_old = {'node1': node_old}

        nodes_new = {'node1': self._get_node_scheme()}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=PROPERTY,
                entity_id='nodes:node1:properties:property1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_node_properties_modify_property(self):

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

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=PROPERTY,
                entity_id='nodes:node1:properties:property1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_node_operations_no_change(self):

        node_old = self._get_node_scheme()
        node_old.update({OPERATIONS: {'full.operation1.name': {
            'operation1_field': 'operation1_field_value'}}})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_extract_steps_from_node_operations_add_operation(self):

        nodes_old = {'node1': self._get_node_scheme()}

        node_new = self._get_node_scheme()
        node_new.update({OPERATIONS: {'full.operation1.name': {
            'operation1_field': 'operation1_field_value'}}})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=OPERATION,
                entity_id='nodes:node1:operations:full.operation1.name')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_node_operations_remove_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({OPERATIONS: {'full.operation1.name': {
            'operation1_field': 'operation1_field_value'}}})
        nodes_old = {'node1': node_old}

        nodes_new = {'node1': self._get_node_scheme()}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=OPERATION,
                entity_id='nodes:node1:operations:full.operation1.name')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_node_operations_modify_operation(self):

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

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=OPERATION,
                entity_id='nodes:node1:operations:full.operation1.name')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_relationships_no_change(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target'}
        ]})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps = self.step_extractor.extract_steps()

        self.assertEquals([], steps)

    def test_extract_steps_from_relationships_add_relationship(self):

        nodes_old = {'node1': self._get_node_scheme()}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target'}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_relationships_remove_relationship(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target'}
        ]})
        nodes_old = {'node1': node_old}

        nodes_new = {'node1': self._get_node_scheme()}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_relationships_change_type(self):

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

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]'),
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_relationships_change_target(self):
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

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]'),
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_relationships_change_type_and_target(self):
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

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]'),
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_relationships_add_source_operation(self):

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

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'source_operations:full.operation1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_relationships_remove_source_operation(self):

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

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'source_operations:full.operation1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_relationships_modify_source_operation(self):

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

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'source_operations:full.operation1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_relationships_add_target_operation(self):

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

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='add',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'target_operations:full.operation1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_relationships_remove_target_operation(self):

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

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='remove',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'target_operations:full.operation1')
        ]

        self.assertEquals(expected_steps, steps)

    def test_extract_steps_from_relationships_modify_target_operation(self):

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

        steps = self.step_extractor.extract_steps()

        expected_steps = [
            models.DeploymentUpdateStep(
                action='modify',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'target_operations:full.operation1')
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

        self.assertEquals(_get_matching_relationship(
            relationship, relationships_with_match),
            {'type': 'typeA', 'target_id': 'id_1', 'field1': 'value1'})

        self.assertIsNone(_get_matching_relationship(
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
                entity_id=''),
            models.DeploymentUpdateStep(
                action='remove',
                entity_type='relationship',
                entity_id=''),
            models.DeploymentUpdateStep(
                action='remove',
                entity_type='node',
                entity_id='')
        ]

        steps.sort()
        self.assertEquals(steps, sorted_steps)

    def test_all_changes_combined(self):

        path_before = get_resource(
            'deployment_update/combined_changes_before.json')

        path_after = get_resource(
            'deployment_update/combined_changes_after.json')

        with open(path_before) as fp_before, open(path_after) as fp_after:
            self.step_extractor.old_deployment_plan = json.load(fp_before)
            self.step_extractor.new_deployment_plan = json.load(fp_after)

        expected_steps = {
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

            'add_workflow': models.DeploymentUpdateStep(
                'add',
                WORKFLOW,
                'workflows:added_workflow',
                ANY),

            'remove_workflow': models.DeploymentUpdateStep(
                'remove',
                WORKFLOW,
                'workflows:removed_workflow',
                ANY),

            'modify_workflow': models.DeploymentUpdateStep(
                'modify',
                WORKFLOW,
                'workflows:modified_workflow',
                ANY)
        }
        steps = self.step_extractor.extract_steps()

        self.assertEquals(set(expected_steps.values()), set(steps))

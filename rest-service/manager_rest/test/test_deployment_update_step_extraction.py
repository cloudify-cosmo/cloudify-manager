import copy
import json

import mock
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
            blueprint=None,
            id='deployment_update_id')

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

        self.step_extractor.extract_steps()

        create_step = \
            self.deployment_update_manager.create_deployment_update_step

        self.assertFalse(create_step.called)

    def test_extract_steps_from_outputs_add_output(self):

        outputs_new = {OUTPUTS: {'output1': 'output1_value'}}

        self.step_extractor.new_deployment_plan.update(outputs_new)

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step.\
            assert_called_once_with(ANY,
                                    'add',
                                    OUTPUT,
                                    'outputs:output1')

    def test_extract_steps_from_outputs_remove_output(self):

        outputs_old = {OUTPUTS: {'output1': 'output1_value'}}

        self.step_extractor.old_deployment_plan.update(outputs_old)

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(ANY,
                                    'remove',
                                    OUTPUT,
                                    'outputs:output1')

    def test_extract_steps_from_outputs_modify_output(self):

        outputs_old = {OUTPUTS: {'output1': 'output1_value'}}
        outputs_new = {OUTPUTS: {'output1': 'output1_modified_value'}}

        self.step_extractor.old_deployment_plan.update(outputs_old)
        self.step_extractor.new_deployment_plan.update(outputs_new)

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(ANY,
                                    'modify',
                                    OUTPUT,
                                    'outputs:output1')

    def test_extract_steps_from_workflows_no_change(self):

        workflows_old = {WORKFLOWS: {'workflow1': 'workflow1_value'}}
        workflows_new = workflows_old

        self.step_extractor.old_deployment_plan.update(workflows_old)
        self.step_extractor.new_deployment_plan.update(workflows_new)

        self.step_extractor.extract_steps()

        create_step = \
            self.deployment_update_manager.create_deployment_update_step

        self.assertFalse(create_step.called)

    def test_extract_steps_from_workflows_add_workflow(self):

        workflows_new = {WORKFLOWS: {'workflow1': 'workflow1_value'}}

        self.step_extractor.new_deployment_plan.update(workflows_new)

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(ANY,
                                    'add',
                                    WORKFLOW,
                                    'workflows:workflow1')

    def test_extract_steps_from_workflows_remove_workflow(self):

        workflows_old = {WORKFLOWS: {'workflow1': 'workflow1_value'}}

        self.step_extractor.old_deployment_plan.update(workflows_old)

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(ANY,
                                    'remove',
                                    WORKFLOW,
                                    'workflows:workflow1')

    def test_extract_steps_from_workflows_modify_workflow(self):

        workflows_old = {WORKFLOWS: {'workflow1': 'workflow1_value'}}
        workflows_new = \
            {WORKFLOWS: {'workflow1': 'workflow1_modified_value'}}

        self.step_extractor.old_deployment_plan.update(workflows_old)
        self.step_extractor.new_deployment_plan.update(workflows_new)

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(ANY,
                                    'modify',
                                    WORKFLOW,
                                    'workflows:workflow1')

    def test_extract_steps_from_nodes_no_change(self):
        nodes_old = {NODES: {'node1': self._get_node_scheme()}}
        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan.update(nodes_old)
        self.step_extractor.new_deployment_plan.update(nodes_new)

        self.step_extractor.extract_steps()

        create_step = \
            self.deployment_update_manager.create_deployment_update_step

        self.assertFalse(create_step.called)

    def test_extract_steps_from_nodes_add_node(self):

        nodes_new = {NODES: {'node1': self._get_node_scheme()}}

        self.step_extractor.new_deployment_plan.update(nodes_new)

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(ANY,
                                    'add',
                                    NODE,
                                    'nodes:node1')

    def test_extract_steps_from_nodes_remove_node(self):

        nodes_old = {NODES: {'node1': self._get_node_scheme()}}

        self.step_extractor.old_deployment_plan.update(nodes_old)

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(ANY,
                                    'remove',
                                    NODE,
                                    'nodes:node1')

    def test_extract_steps_from_nodes_add_and_remove_node_changed_type(self):
        node_old = self._get_node_scheme()
        node_old.update({TYPE: 'old_type'})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({TYPE: 'new_type'})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        self.step_extractor.extract_steps()

        add_node_call = mock.call(
            ANY,
            'add',
            NODE,
            'nodes:node1')

        remove_node_call = mock.call(
            ANY,
            'remove',
            NODE,
            'nodes:node1')

        create_step = \
            self.deployment_update_manager.create_deployment_update_step

        create_step_calls = create_step.call_args_list
        self.assertTrue(add_node_call in create_step_calls)
        self.assertTrue(remove_node_call in create_step_calls)
        self.assertEquals(len(create_step_calls), 2)

    def test_extract_steps_from_node_properties_no_change(self):

        node_old = self._get_node_scheme()
        node_old.update({PROPERTIES: {'property1': 'property1_value'}})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        self.step_extractor.extract_steps()

        create_step = \
            self.deployment_update_manager.create_deployment_update_step

        self.assertFalse(create_step.called)

    def test_extract_steps_from_node_properties_add_property(self):

        nodes_old = {'node1': self._get_node_scheme()}

        node_new = self._get_node_scheme()
        node_new.update({PROPERTIES: {'property1': 'property1_value'}})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'add',
             PROPERTY,
             'nodes:node1:properties:property1')

    def test_extract_steps_from_node_properties_remove_property(self):

        node_old = self._get_node_scheme()
        node_old.update({PROPERTIES: {'property1': 'property1_value'}})
        nodes_old = {'node1': node_old}

        nodes_new = {'node1': self._get_node_scheme()}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'remove',
             PROPERTY,
             'nodes:node1:properties:property1')

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

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'modify',
             PROPERTY,
             'nodes:node1:properties:property1')

    def test_extract_steps_from_node_operations_no_change(self):

        node_old = self._get_node_scheme()
        node_old.update({OPERATIONS: {'full.operation1.name': {
            'operation1_field': 'operation1_field_value'}}})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        self.step_extractor.extract_steps()

        create_step = \
            self.deployment_update_manager.create_deployment_update_step

        self.assertFalse(create_step.called)

    def test_extract_steps_from_node_operations_add_operation(self):

        nodes_old = {'node1': self._get_node_scheme()}

        node_new = self._get_node_scheme()
        node_new.update({OPERATIONS: {'full.operation1.name': {
            'operation1_field': 'operation1_field_value'}}})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'add',
             OPERATION,
             'nodes:node1:operations:full.operation1.name')

    def test_extract_steps_from_node_operations_remove_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({OPERATIONS: {'full.operation1.name': {
            'operation1_field': 'operation1_field_value'}}})
        nodes_old = {'node1': node_old}

        nodes_new = {'node1': self._get_node_scheme()}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'remove',
             OPERATION,
             'nodes:node1:operations:full.operation1.name')

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

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'modify',
             OPERATION,
             'nodes:node1:operations:full.operation1.name')

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

        self.step_extractor.extract_steps()

        create_step = \
            self.deployment_update_manager.create_deployment_update_step

        self.assertFalse(create_step.called)

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

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'add',
             RELATIONSHIP,
             'nodes:node1:relationships:[0]')

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

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'remove',
             RELATIONSHIP,
             'nodes:node1:relationships:[0]')

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

        self.step_extractor.extract_steps()

        add_relationship_call = mock.call(
            ANY,
            'add',
            RELATIONSHIP,
            'nodes:node1:relationships:[0]')

        remove_relationship_call = mock.call(
            ANY,
            'remove',
            RELATIONSHIP,
            'nodes:node1:relationships:[0]')

        create_step = \
            self.deployment_update_manager.create_deployment_update_step

        create_step_calls = create_step.call_args_list
        self.assertTrue(add_relationship_call in create_step_calls)
        self.assertTrue(remove_relationship_call in create_step_calls)
        self.assertEquals(len(create_step_calls), 2)

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

        self.step_extractor.extract_steps()

        add_relationship_call = mock.call(
            ANY,
            'add',
            RELATIONSHIP,
            'nodes:node1:relationships:[0]')
        remove_relationship_call = mock.call(
            ANY,
            'remove',
            RELATIONSHIP,
            'nodes:node1:relationships:[0]')
        create_step = \
            self.deployment_update_manager.create_deployment_update_step

        create_step_calls = create_step.call_args_list
        self.assertTrue(add_relationship_call in create_step_calls)
        self.assertTrue(remove_relationship_call in create_step_calls)
        self.assertEquals(len(create_step_calls), 2)

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

        self.step_extractor.extract_steps()

        add_relationship_call = mock.call(
            ANY,
            'add',
            RELATIONSHIP,
            'nodes:node1:relationships:[0]')
        remove_relationship_call = mock.call(
            ANY,
            'remove',
            RELATIONSHIP,
            'nodes:node1:relationships:[0]')
        create_step = \
            self.deployment_update_manager.create_deployment_update_step

        create_step_calls = create_step.call_args_list
        self.assertTrue(add_relationship_call in create_step_calls)
        self.assertTrue(remove_relationship_call in create_step_calls)
        self.assertEquals(len(create_step_calls), 2)

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

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'add',
             OPERATION,
             'nodes:node1:relationships:[0]:source_operations:full.operation1')

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

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'remove',
             OPERATION,
             'nodes:node1:relationships:[0]:source_operations:full.operation1')

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

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'modify',
             OPERATION,
             'nodes:node1:relationships:[0]:source_operations:full.operation1')

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

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'add',
             OPERATION,
             'nodes:node1:relationships:[0]:target_operations:full.operation1')

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

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'remove',
             OPERATION,
             'nodes:node1:relationships:[0]:target_operations:full.operation1')

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

        self.step_extractor.extract_steps()

        self.deployment_update_manager.create_deployment_update_step. \
            assert_called_once_with(
             ANY,
             'modify',
             OPERATION,
             'nodes:node1:relationships:[0]:target_operations:full.operation1')

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

    def test_all_changes_combined(self):

        path_before = get_resource(
            'deployment_update/combined_changes_before.json')

        path_after = get_resource(
            'deployment_update/combined_changes_after.json')

        with open(path_before) as fp_before, open(path_after) as fp_after:
            self.step_extractor.old_deployment_plan = json.load(fp_before)
            self.step_extractor.new_deployment_plan = json.load(fp_after)

        expected_calls = {
            'remove_node': mock.call(
                'deployment_update_id',
                'remove',
                NODE,
                'nodes:node1'),

            'add_node': mock.call(
                'deployment_update_id',
                'add',
                NODE,
                'nodes:node2'),

            'add_node_changed_type': mock.call(
                'deployment_update_id',
                'add',
                NODE,
                'nodes:node3'),

            'remove_node_changed_type': mock.call(
                'deployment_update_id',
                'remove',
                NODE,
                'nodes:node3'),

            'add_property': mock.call(
                'deployment_update_id',
                'add',
                PROPERTY,
                'nodes:node4:properties:added_prop'),

            'remove_property': mock.call(
                'deployment_update_id',
                'remove',
                PROPERTY,
                'nodes:node4:properties:removed_prop'),

            'modify_property': mock.call(
                'deployment_update_id',
                'modify',
                PROPERTY,
                'nodes:node4:properties:modified_prop'),

            'remove_relationship': mock.call(
                'deployment_update_id',
                'remove',
                RELATIONSHIP,
                'nodes:node6:relationships:[0]'),

            'add_relationship': mock.call(
                'deployment_update_id',
                'add',
                RELATIONSHIP,
                'nodes:node7:relationships:[0]'),

            'remove_relationship_changed_type': mock.call(
                'deployment_update_id',
                'remove',
                RELATIONSHIP,
                'nodes:node8:relationships:[0]'),

            'add_relationship_changed_type': mock.call(
                'deployment_update_id',
                'add',
                RELATIONSHIP,
                'nodes:node8:relationships:[0]'),

            'remove_relationship_changed_target': mock.call(
                'deployment_update_id',
                'remove',
                RELATIONSHIP,
                'nodes:node9:relationships:[0]'),

            'add_relationship_changed_target': mock.call(
                'deployment_update_id',
                'add',
                RELATIONSHIP,
                'nodes:node9:relationships:[0]'),

            'remove_relationship_changed_type_and_target': mock.call(
                'deployment_update_id',
                'remove',
                RELATIONSHIP,
                'nodes:node10:relationships:[0]'),

            'add_relationship_changed_type_and_target': mock.call(
                'deployment_update_id',
                'add',
                RELATIONSHIP,
                'nodes:node10:relationships:[0]'),

            'add_operation': mock.call(
                'deployment_update_id',
                'add',
                OPERATION,
                'nodes:node11:operations:interface1.added_operation'),

            'add_operation_shortened': mock.call(
                'deployment_update_id',
                'add',
                OPERATION,
                'nodes:node11:operations:added_operation'),

            'remove_operation': mock.call(
                'deployment_update_id',
                'remove',
                OPERATION,
                'nodes:node11:operations:interface1.removed_operation'),

            'remove_operation_shortened': mock.call(
                'deployment_update_id',
                'remove',
                OPERATION,
                'nodes:node11:operations:removed_operation'),

            'modify_operation': mock.call(
                'deployment_update_id',
                'modify',
                OPERATION,
                'nodes:node11:operations:interface1.modified_operation'),

            'modify_operation_shortened': mock.call(
                'deployment_update_id',
                'modify',
                OPERATION,
                'nodes:node11:operations:modified_operation'),

            'add_relationship_operation': mock.call(
                'deployment_update_id',
                'add',
                OPERATION,
                'nodes:node12:relationships:[0]:target_operations:'
                'interface_for_modified_and_added.added_operation'),

            'add_relationship_operation_shortened': mock.call(
                'deployment_update_id',
                'add',
                OPERATION,
                'nodes:node12:relationships:[0]:target_operations:'
                'added_operation'),


            'remove_relationship_operation': mock.call(
                'deployment_update_id',
                'remove',
                OPERATION,
                'nodes:node12:relationships:[0]:source_operations:'
                'interface_for_intact_and_removed.removed_operation'),

            'remove_relationship_operation_shortened': mock.call(
                'deployment_update_id',
                'remove',
                OPERATION,
                'nodes:node12:relationships:[0]:source_operations:'
                'removed_operation'),

            'modify_relationship_operation': mock.call(
                'deployment_update_id',
                'modify',
                OPERATION,
                'nodes:node12:relationships:[0]:target_operations:'
                'interface_for_modified_and_added.modified_operation'),

            'modify_relationship_operation_shortened': mock.call(
                'deployment_update_id',
                'modify',
                OPERATION,
                'nodes:node12:relationships:[0]:target_operations:'
                'modified_operation'),

            'add_output': mock.call(
                'deployment_update_id',
                'add',
                OUTPUT,
                'outputs:added_output'),

            'remove_output': mock.call(
                'deployment_update_id',
                'remove',
                OUTPUT,
                'outputs:removed_output'),

            'modify_output': mock.call(
                'deployment_update_id',
                'modify',
                OUTPUT,
                'outputs:modified_output'),

            'add_workflow': mock.call(
                'deployment_update_id',
                'add',
                WORKFLOW,
                'workflows:added_workflow'),

            'remove_workflow': mock.call(
                'deployment_update_id',
                'remove',
                WORKFLOW,
                'workflows:removed_workflow'),

            'modify_workflow': mock.call(
                'deployment_update_id',
                'modify',
                WORKFLOW,
                'workflows:modified_workflow')
        }
        self.step_extractor.extract_steps()

        create_step = \
            self.deployment_update_manager.create_deployment_update_step

        # test that all the expected calls were called
        create_step.assert_has_calls(
            expected_calls.values(),
            any_order=True)
        # test that no other calls were made
        self.assertEquals(create_step.call_count, len(expected_calls))

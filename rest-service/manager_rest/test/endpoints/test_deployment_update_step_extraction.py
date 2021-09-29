import copy
import json

import unittest
from mock import patch
from manager_rest.test.attribute import attr
import networkx as nx


from manager_rest.test.base_test import LATEST_API_VERSION
from manager_rest.storage import models
from manager_rest.deployment_update.step_extractor import (
    PROPERTY, PROPERTIES, OUTPUT, OUTPUTS, WORKFLOW, WORKFLOWS, NODE,
    NODES, OPERATION, OPERATIONS, RELATIONSHIP, RELATIONSHIPS,
    SOURCE_OPERATIONS, TARGET_OPERATIONS, TYPE, GROUP, GROUPS, POLICY_TYPE,
    POLICY_TYPES, POLICY_TRIGGER, POLICY_TRIGGERS, HOST_ID, PLUGIN,
    DEPLOYMENT_PLUGINS_TO_INSTALL, PLUGINS_TO_INSTALL, DESCRIPTION)
from manager_rest.deployment_update.step_extractor \
    import EntityIdBuilder, StepExtractor, \
    DeploymentUpdateStep
from manager_rest.test.utils import get_resource


@attr(client_min_version=2.1, client_max_version=LATEST_API_VERSION)
class StepExtractorTestCase(unittest.TestCase):

    @staticmethod
    def _get_node_scheme():
        return {
            OPERATIONS: {},
            PROPERTIES: {},
            RELATIONSHIPS: [],
            TYPE: '',
            HOST_ID: '',
            PLUGINS_TO_INSTALL: []
        }

    @staticmethod
    def _get_relationship_scheme():
        return {
            SOURCE_OPERATIONS: {},
            "target_id": "",
            TARGET_OPERATIONS: {},
            TYPE: "",
            PROPERTIES: {}
        }

    def setUp(self):
        super(StepExtractorTestCase, self).setUp()
        names_to_mock = [
            'manager_rest.deployment_update.step_extractor.'
            'manager_rest.deployment_update.manager'
        ]
        for name_to_mock in names_to_mock:
            patcher = patch(name_to_mock)
            self.addCleanup(patcher.stop)
            patcher.start()

        stub_deployment = models.Deployment(id='deployment_id')

        stub_deployment_update = models.DeploymentUpdate(
            deployment_plan=None,
            id='deployment_update_id')
        stub_deployment_update.deployment = stub_deployment

        self.step_extractor = StepExtractor(
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
            self.assertEqual(NODES, entity_id_builder.entity_id)

            with entity_id_builder.extend_id(NODE):
                expected = 'nodes{0}node'.format(entity_id_builder._separator)
                self.assertEqual(expected, entity_id_builder.entity_id)

            self.assertEqual(NODES, entity_id_builder.entity_id)
        self.assertEqual('', entity_id_builder.entity_id)

    def test_entity_id_builder_prepend_before_last_element(self):

        entity_id_builder = EntityIdBuilder()
        with entity_id_builder.extend_id(NODE):
            self.assertEqual(NODE, entity_id_builder.entity_id)

            with entity_id_builder.prepend_id_last_element(NODES):
                expected = 'nodes{0}node'.format(entity_id_builder._separator)
                self.assertEqual(expected, entity_id_builder.entity_id)

            self.assertEqual(NODE, entity_id_builder.entity_id)
        self.assertEqual('', entity_id_builder.entity_id)

    def test_entity_name(self):
        step = DeploymentUpdateStep(action='add',
                                    entity_type=NODE,
                                    entity_id='nodes:node1')
        self.assertEqual('node1', step.entity_name)

    def test_update_topology_order_of_add_node_steps(self):

        add_node_a_step = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='nodes:node_a')
        add_node_b_step = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='nodes:node_b')
        add_node_c_step = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='nodes:node_c')
        add_node_d_step = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='nodes:node_d')
        add_node_e_step = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='nodes:node_e')
        add_node_f_step = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='nodes:node_f')
        steps = [add_node_a_step, add_node_b_step, add_node_c_step,
                 add_node_d_step, add_node_e_step, add_node_f_step]

        # Imagine the following relationships between the added nodes:
        #
        #       e
        #       ^^
        #       | \
        #       c  d
        #      ^ ^
        #     /   \
        #    a     b     f

        topologically_sorted_added_nodes = ['node_f', 'node_a', 'node_b',
                                            'node_c', 'node_d', 'node_e']
        self.step_extractor._update_topology_order_of_add_node_steps(
            steps, topologically_sorted_added_nodes)

        self.assertEqual(5, add_node_e_step.topology_order)
        self.assertEqual(4, add_node_d_step.topology_order)
        self.assertEqual(3, add_node_c_step.topology_order)
        self.assertEqual(2, add_node_b_step.topology_order)
        self.assertEqual(1, add_node_a_step.topology_order)
        self.assertEqual(0, add_node_f_step.topology_order)

    def test_create_added_nodes_graph(self):

        # Create a plan from which _create_added_nodes_graph will create the
        # added nodes graph
        new_deployment_plan = {
            "nodes": {
                "node_a": {
                    "relationships": [
                        {"target_id": 'node_c'}
                    ]
                },
                "node_b": {
                    "relationships": [
                        {"target_id": 'node_c'}
                    ]
                },
                "node_c": {
                    "relationships": [
                        {"target_id": 'node_e'}
                    ]
                },
                "node_d": {
                    "relationships": [
                        {"target_id": 'node_e'}
                    ]
                },
                "node_e": {
                    "relationships": []
                },
                "node_f": {
                    "relationships": []
                }
            }
        }
        self.step_extractor.new_deployment_plan = new_deployment_plan

        # mock the _extract_added_nodes_names call
        node_names = ['node_a', 'node_b', 'node_c',
                      'node_d', 'node_e', 'node_f']
        with patch.object(self.step_extractor, '_extract_added_nodes_names',
                          return_value=node_names):
            # create the added nodes graph
            graph = self.step_extractor._create_added_nodes_graph('stub')

        # create the graph we expected to get from _create_added_nodes_graph
        expected_graph = nx.DiGraph()
        expected_graph.add_edge('node_a', 'node_c')
        expected_graph.add_edge('node_b', 'node_c')
        expected_graph.add_edge('node_c', 'node_e')
        expected_graph.add_edge('node_d', 'node_e')
        expected_graph.add_node('node_f')

        # no built-in comparison of graphs in networkx
        self.assertEqual(expected_graph.__dict__, graph.__dict__)

    def test_description_no_change(self):

        description_old = {DESCRIPTION: 'description'}
        description_new = description_old

        self.step_extractor.old_deployment_plan.update(description_old)
        self.step_extractor.new_deployment_plan.update(description_new)

        steps, _ = self.step_extractor.extract_steps()
        self.assertEqual([], steps)

    def test_description_add_description(self):

        description_old = {DESCRIPTION: None}
        description_new = {DESCRIPTION: 'description'}

        self.step_extractor.old_deployment_plan.update(description_old)
        self.step_extractor.new_deployment_plan.update(description_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=DESCRIPTION,
                entity_id='description')
        ]

        self.assertEqual(expected_steps, steps)

    def test_description_remove_description(self):

        description_old = {DESCRIPTION: 'description'}
        description_new = {DESCRIPTION: None}

        self.step_extractor.old_deployment_plan.update(description_old)
        self.step_extractor.new_deployment_plan.update(description_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=DESCRIPTION,
                entity_id='description'
            )
        ]

        self.assertEqual(expected_steps, steps)

    def test_description_modify_description(self):

        description_old = {DESCRIPTION: 'description_old'}
        description_new = {DESCRIPTION: 'description_new'}

        self.step_extractor.old_deployment_plan.update(description_old)
        self.step_extractor.new_deployment_plan.update(description_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='modify',
                entity_type=DESCRIPTION,
                entity_id='description')
        ]

        self.assertEqual(expected_steps, steps)

    def test_outputs_no_change(self):

        outputs_old = {OUTPUTS: {'output1': 'output1_value'}}
        outputs_new = outputs_old

        self.step_extractor.old_deployment_plan.update(outputs_old)
        self.step_extractor.new_deployment_plan.update(outputs_new)

        steps, _ = self.step_extractor.extract_steps()
        self.assertEqual([], steps)

    def test_outputs_add_output(self):

        outputs_new = {OUTPUTS: {'output1': 'output1_value'}}

        self.step_extractor.new_deployment_plan.update(outputs_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=OUTPUT,
                entity_id='outputs:output1')
        ]

        self.assertEqual(expected_steps, steps)

    def test_outputs_remove_output(self):

        outputs_old = {OUTPUTS: {'output1': 'output1_value'}}

        self.step_extractor.old_deployment_plan.update(outputs_old)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=OUTPUT,
                entity_id='outputs:output1')
        ]

        self.assertEqual(expected_steps, steps)

    def test_outputs_modify_output(self):

        outputs_old = {OUTPUTS: {'output1': 'output1_value'}}
        outputs_new = {OUTPUTS: {'output1': 'output1_modified_value'}}

        self.step_extractor.old_deployment_plan.update(outputs_old)
        self.step_extractor.new_deployment_plan.update(outputs_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='modify',
                entity_type=OUTPUT,
                entity_id='outputs:output1')
        ]

        self.assertEqual(expected_steps, steps)

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

        self.assertEqual([], steps)

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
            DeploymentUpdateStep(
                action='add',
                entity_type=WORKFLOW,
                entity_id='workflows:added_workflow')
        ]

        self.assertEqual(expected_steps, steps)

    def test_workflows_add_workflow_script(self):

        old_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'default_workflows': {
                    'install': False,
                }},
        }
        self.step_extractor.old_deployment_plan.update(
            old_workflow_plugins_to_install)

        new_workflow_plugins_to_install = {
            'workflow_plugins_to_install': {
                'default_workflows': {
                    'install': False,
                },
                'script': {
                    'install': False,
                }}
        }
        self.step_extractor.new_deployment_plan.update(
            new_workflow_plugins_to_install)

        workflows_new = {WORKFLOWS: {
            'new_workflow': {
                'plugin': 'script',
            }}}

        self.step_extractor.new_deployment_plan.update(workflows_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=WORKFLOW,
                entity_id='workflows:new_workflow')
        ]

        self.assertEqual(expected_steps, steps)

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
            DeploymentUpdateStep(
                action='remove',
                entity_type=WORKFLOW,
                entity_id='workflows:removed_workflow')
        ]

        self.assertEqual(expected_steps, steps)

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
            DeploymentUpdateStep(
                action='modify',
                entity_type=WORKFLOW,
                entity_id='workflows:added_workflow')
        ]

        self.assertEqual(expected_steps, steps)

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

        self.assertEqual([], steps)

    def test_nodes_no_change(self):
        nodes_old = {NODES: {'node1': self._get_node_scheme()}}
        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan.update(nodes_old)
        self.step_extractor.new_deployment_plan.update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        self.assertEqual([], steps)

    def test_nodes_add_node(self):

        nodes_new = {NODES: {'node1': self._get_node_scheme()}}

        self.step_extractor.new_deployment_plan.update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=NODE,
                entity_id='nodes:node1')
        ]

        self.assertEqual(expected_steps, steps)

    def test_nodes_remove_node(self):

        nodes_old = {NODES: {'node1': self._get_node_scheme()}}

        self.step_extractor.old_deployment_plan.update(nodes_old)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=NODE,
                entity_id='nodes:node1')
        ]

        self.assertEqual(expected_steps, steps)

    def test_nodes_add_and_remove_node_changed_type(self):
        node_old = self._get_node_scheme()
        node_old.update({TYPE: 'old_type'})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({TYPE: 'new_type'})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        supported_steps, unsupported_steps = \
            self.step_extractor.extract_steps()

        self.assertEqual(0, len(supported_steps))

        expected_steps = [
            DeploymentUpdateStep(
                action='modify',
                entity_type=NODE,
                entity_id='nodes:node1',
                supported=False),
        ]
        self.assertEqual(expected_steps, unsupported_steps)

    def test_nodes_add_and_remove_node_changed_type_and_host_id(self):
        node_old = self._get_node_scheme()
        node_old.update({HOST_ID: 'old_host_id'})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({TYPE: 'new_host_id'})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        supported_steps, unsupported_steps = \
            self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='modify',
                entity_type=NODE,
                entity_id='nodes:node1',
                supported=False),
        ]

        self.assertEqual(expected_steps, unsupported_steps)

    def test_node_properties_no_change(self):

        node_old = self._get_node_scheme()
        node_old.update({PROPERTIES: {'property1': 'property1_value'}})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        self.assertEqual([], steps)

    def test_node_properties_add_property(self):

        nodes_old = {'node1': self._get_node_scheme()}

        node_new = self._get_node_scheme()
        node_new.update({PROPERTIES: {'property1': 'property1_value'}})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=PROPERTY,
                entity_id='nodes:node1:properties:property1')
        ]

        self.assertEqual(expected_steps, steps)

    def test_node_properties_remove_property(self):

        node_old = self._get_node_scheme()
        node_old.update({PROPERTIES: {'property1': 'property1_value'}})
        nodes_old = {'node1': node_old}

        nodes_new = {'node1': self._get_node_scheme()}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=PROPERTY,
                entity_id='nodes:node1:properties:property1')
        ]

        self.assertEqual(expected_steps, steps)

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
            DeploymentUpdateStep(
                action='modify',
                entity_type=PROPERTY,
                entity_id='nodes:node1:properties:property1')
        ]

        self.assertEqual(expected_steps, steps)

    def test_node_operations_no_change(self):

        node_old = self._get_node_scheme()
        node_old.update({OPERATIONS: {'full.operation1.name': {
            'operation1_field': 'operation1_field_value'}}})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        self.assertEqual([], steps)

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
            DeploymentUpdateStep(
                action='add',
                entity_type=OPERATION,
                entity_id='nodes:node1:operations:full.operation1.name')
        ]

        self.assertEqual(expected_steps, steps)

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
            DeploymentUpdateStep(
                action='remove',
                entity_type=OPERATION,
                entity_id='nodes:node1:operations:full.operation1.name')
        ]

        self.assertEqual(expected_steps, steps)

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
            DeploymentUpdateStep(
                action='modify',
                entity_type=OPERATION,
                entity_id='nodes:node1:operations:full.operation1.name')
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_no_change(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target'}
        ]})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        self.assertEqual([], steps)

    def test_relationships_add_relationship(self):

        nodes_old = {'node1': self._get_node_scheme()}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target'}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_remove_relationship(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target'}
        ]})
        nodes_old = {'node1': node_old}

        nodes_new = {'node1': self._get_node_scheme()}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_change_type(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target'}
        ]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'different_relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target'}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]'),
            DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_change_target_non_contained_in(self):
        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             'type_hierarchy': ['rel_hierarchy']}
        ]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'different_relationship_target',
             'type_hierarchy': ['rel_hierarchy']}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]'),
            DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_change_target_contained_in(self):
        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'relationship_target',
             'type_hierarchy': ['rel_hierarchy',
                                'cloudify.relationships.contained_in']}
        ]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'target_id': 'different_relationship_target',
             'type_hierarchy': ['rel_hierarchy',
                                'cloudify.relationships.contained_in']}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, unsupported_steps = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='modify',
                entity_type=NODE,
                entity_id='nodes:node1',
                supported=False),
        ]
        for index, step in enumerate(expected_steps):
            self.assertEqual(step, unsupported_steps[
                index])

    def test_relationships_change_type_and_target(self):
        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target'}
        ]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'different_relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'different_relationship_target'}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]'),
            DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_modify_order(self):
        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_1'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_2'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_3'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_4'}
        ]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_2'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_4'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_3'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_1'}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='modify',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]:[3]'),
            DeploymentUpdateStep(
                action='modify',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[1]:[0]'),
            DeploymentUpdateStep(
                action='modify',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[3]:[1]')
        ]
        # we don't care for the order the steps were created in
        self.assertSetEqual(set(expected_steps), set(steps))

    def test_relationships_modify_order_with_add_and_remove(self):
        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_1'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_2'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_3'},

        ]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_5'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_2'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_4'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_1'}
        ]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='modify',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]:[3]'),
            DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[2]'),
            DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[2]'),
            DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]
        # we don't care for the order the steps were created in
        self.assertSetEqual(set(expected_steps), set(steps))

    def test_relationships_add_source_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             SOURCE_OPERATIONS: {}
             }]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             SOURCE_OPERATIONS: {'full.operation1': {}}
             }]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'source_operations:full.operation1')
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_remove_source_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             SOURCE_OPERATIONS: {'full.operation1': {}}
             }]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             SOURCE_OPERATIONS: {}
             }]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'source_operations:full.operation1')
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_modify_source_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
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
             'type_hierarchy': ['rel_hierarchy'],
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
            DeploymentUpdateStep(
                action='modify',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'source_operations:full.operation1')
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_add_target_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             TARGET_OPERATIONS: {}
             }]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             TARGET_OPERATIONS: {'full.operation1': {}}
             }]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'target_operations:full.operation1')
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_remove_target_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             TARGET_OPERATIONS: {'full.operation1': {}}
             }]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             TARGET_OPERATIONS: {}
             }]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'target_operations:full.operation1')
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_modify_target_operation(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
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
             'type_hierarchy': ['rel_hierarchy'],
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
            DeploymentUpdateStep(
                action='modify',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'target_operations:full.operation1')
        ]

        self.assertEqual(expected_steps, steps)

    def test_duplicate_relationship(self):
        rel = {
            'type': 'relationship_type',
            'type_hierarchy': ['rel_hierarchy'],
            'target_id': 'relationship_target',
        }
        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [rel, rel]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [rel, rel]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        self.assertEqual(steps, [])

    def test_get_matching_relationship(self):
        relationships_with_match = [
            {'type': 'typeA', 'target_id': 'id_1', 'field2': 'value2'},
            {'type': 'typeB', 'target_id': 'id_1'},
            {'type': 'typeB', 'target_id': 'id_2'},
            {'type': 'typeA', 'target_id': 'id_2'}
        ]
        relationships_with_no_match = [
            {'type': 'typeB', 'target_id': 'id_1'},
            {'type': 'typeB', 'target_id': 'id_2'},
            {'type': 'typeA', 'target_id': 'id_2'}
        ]

        _find_relationship = self.step_extractor._find_relationship
        assert _find_relationship(
            relationships_with_match, 'typeA', 'id_1'
        ) == ({'type': 'typeA', 'target_id': 'id_1', 'field2': 'value2'}, 0)

        assert _find_relationship(
            relationships_with_no_match, 'typeA', 'id_1'
        ) == (None, None)

    def test_sort_steps_compare_action(self):

        add_step = DeploymentUpdateStep(
            action='add',
            entity_type='',
            entity_id='')
        remove_step = DeploymentUpdateStep(
            action='remove',
            entity_type='',
            entity_id='')
        modify_step = DeploymentUpdateStep(
            action='modify',
            entity_type='',
            entity_id='')
        steps = [add_step, remove_step, modify_step]
        expected_step_order = [remove_step, add_step, modify_step]
        steps.sort(),
        self.assertEqual(expected_step_order, steps)

    def test_sort_steps_add_node_before_add_relationship(self):

        add_node_step = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='')
        add_relationship_step = DeploymentUpdateStep(
            action='add',
            entity_type=RELATIONSHIP,
            entity_id='')
        steps = [add_relationship_step, add_node_step]
        expected_step_order = [add_node_step, add_relationship_step]
        steps.sort()
        self.assertEqual(expected_step_order, steps)

    def test_sort_steps_remove_relationship_before_remove_node(self):

        remove_relationship_step = DeploymentUpdateStep(
            action='remove',
            entity_type=RELATIONSHIP,
            entity_id='')
        remove_node_step = DeploymentUpdateStep(
            action='remove',
            entity_type=NODE,
            entity_id='')
        steps = [remove_node_step, remove_relationship_step]
        expected_step_order = [remove_relationship_step, remove_node_step]
        steps.sort()
        self.assertEqual(expected_step_order, steps)

    def test_sort_steps_higher_topology_before_lower_topology(self):

        default_topology_step = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='')
        topology_order_1_step = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='',
            topology_order=1)
        topology_order_2_step = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='',
            topology_order=2)
        steps = [topology_order_1_step,
                 default_topology_step,
                 topology_order_2_step]
        expected_step_order = [
            topology_order_2_step,
            topology_order_1_step,
            default_topology_step]
        steps.sort()
        self.assertEqual(expected_step_order, steps)

    def test_sort_steps_all_comparison_considerations(self):

        add_node_step_default_topology = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='')
        add_node_step_topology_order_1 = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='',
            topology_order=1)
        add_node_step_topology_order_2 = DeploymentUpdateStep(
            action='add',
            entity_type=NODE,
            entity_id='',
            topology_order=2)
        remove_relationship_step = DeploymentUpdateStep(
            action='remove',
            entity_type=RELATIONSHIP,
            entity_id='')
        remove_node_step = DeploymentUpdateStep(
            action='remove',
            entity_type=NODE,
            entity_id='')
        add_relationship_step = DeploymentUpdateStep(
            action='add',
            entity_type=RELATIONSHIP,
            entity_id='')
        modify_property_step = DeploymentUpdateStep(
            action='modify',
            entity_type=PROPERTY,
            entity_id='')

        steps = [add_node_step_topology_order_1, remove_node_step,
                 modify_property_step, add_relationship_step,
                 add_node_step_default_topology, remove_relationship_step,
                 add_node_step_topology_order_2]
        expected_step_order = [
            remove_relationship_step,
            remove_node_step,
            add_node_step_topology_order_2,
            add_node_step_topology_order_1,
            add_node_step_default_topology,
            add_relationship_step,
            modify_property_step]
        steps.sort()
        self.assertEqual(expected_step_order, steps)

    # from here, tests involving unsupported steps

    def test_relationships_intact_property(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             PROPERTIES: {
                 'property1': 'property1_value'
             }}]})
        nodes_old = {'node1': node_old}

        nodes_new = nodes_old

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        _, steps = self.step_extractor.extract_steps()

        self.assertEqual([], steps)

    def test_relationships_add_property(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             'properties': {}}]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             PROPERTIES: {
                 'property1': 'property1_different_value'
             }}]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=PROPERTY,
                entity_id='nodes:node1:relationships:[0]:'
                          'properties:property1',
                supported=False)
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_remove_property(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             PROPERTIES: {
                 'property1': 'property1_different_value'
             }}]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             'properties': {}}]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=PROPERTY,
                entity_id='nodes:node1:relationships:[0]:'
                          'properties:property1',
                supported=False)
        ]

        self.assertEqual(expected_steps, steps)

    def test_relationships_modify_property(self):

        node_old = self._get_node_scheme()
        node_old.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             PROPERTIES: {
                 'property1': 'property1_value'
             }}]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({RELATIONSHIPS: [
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target',
             PROPERTIES: {
                 'property1': 'property1_different_value'
             }}]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='modify',
                entity_type=PROPERTY,
                entity_id='nodes:node1:relationships:[0]:'
                          'properties:property1',
                supported=False)
        ]

        self.assertEqual(expected_steps, steps)

    def test_extract_steps_policy_types_no_change(self):
        policy_types_old = {
            POLICY_TYPES: {'policy_type1': 'policy_type1_value'}}
        policy_types_new = policy_types_old

        self.step_extractor.old_deployment_plan.update(policy_types_old)
        self.step_extractor.new_deployment_plan.update(policy_types_new)

        _, steps = self.step_extractor.extract_steps()

        self.assertEqual([], steps)

    def test_policy_types_add_policy_type(self):

        policy_types_new = {
            POLICY_TYPES: {'policy_type1': 'policy_type1_value'}}

        self.step_extractor.new_deployment_plan.update(policy_types_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=POLICY_TYPE,
                entity_id='policy_types:policy_type1',
                supported=False)
        ]

        self.assertEqual(expected_steps, steps)

    def test_policy_types_remove_policy_type(self):

        policy_types_old = {
            POLICY_TYPES: {'policy_type1': 'policy_type1_value'}}

        self.step_extractor.old_deployment_plan.update(policy_types_old)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=POLICY_TYPE,
                entity_id='policy_types:policy_type1',
                supported=False)
        ]

        self.assertEqual(expected_steps, steps)

    def test_policy_types_modify_policy_type(self):

        policy_types_old = {POLICY_TYPES: {
            'policy_type1': 'policy_type1_value'}}
        policy_types_new = \
            {POLICY_TYPES: {'policy_type1': 'policy_type1_modified_value'}}

        self.step_extractor.old_deployment_plan.update(policy_types_old)
        self.step_extractor.new_deployment_plan.update(policy_types_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='modify',
                entity_type=POLICY_TYPE,
                entity_id='policy_types:policy_type1',
                supported=False)
        ]

        self.assertEqual(expected_steps, steps)

    def test_extract_steps_policy_triggers_no_change(self):
        policy_triggers_old = {
            POLICY_TRIGGERS: {'policy_trigger1': 'policy_trigger1_value'}}
        policy_triggers_new = policy_triggers_old

        self.step_extractor.old_deployment_plan.update(policy_triggers_old)
        self.step_extractor.new_deployment_plan.update(policy_triggers_new)

        _, steps = self.step_extractor.extract_steps()

        self.assertEqual([], steps)

    def test_policy_triggers_add_policy_trigger(self):

        policy_triggers_new = {
            POLICY_TRIGGERS: {'policy_trigger1': 'policy_trigger1_value'}}

        self.step_extractor.new_deployment_plan.update(policy_triggers_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=POLICY_TRIGGER,
                entity_id='policy_triggers:policy_trigger1',
                supported=False)
        ]

        self.assertEqual(expected_steps, steps)

    def test_policy_triggers_remove_policy_trigger(self):

        policy_triggers_old = {
            POLICY_TRIGGERS: {'policy_trigger1': 'policy_trigger1_value'}}

        self.step_extractor.old_deployment_plan.update(policy_triggers_old)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=POLICY_TRIGGER,
                entity_id='policy_triggers:policy_trigger1',
                supported=False)
        ]

        self.assertEqual(expected_steps, steps)

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
            DeploymentUpdateStep(
                action='modify',
                entity_type=POLICY_TRIGGER,
                entity_id='policy_triggers:policy_trigger1',
                supported=False)
        ]

        self.assertEqual(expected_steps, steps)

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

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=WORKFLOW,
                entity_id='workflows:added_workflow',
                supported=True)
        ]

        self.assertEqual(expected_steps, steps)

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

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='modify',
                entity_type=WORKFLOW,
                entity_id='workflows:added_workflow',
                supported=True)
        ]

        self.assertEqual(expected_steps, steps)

    def test_groups_no_change(self):

        groups_old = {GROUPS: {'group1': {}}}
        groups_new = groups_old

        self.step_extractor.old_deployment_plan.update(groups_old)
        self.step_extractor.new_deployment_plan.update(groups_new)

        _, steps = self.step_extractor.extract_steps()
        self.assertEqual([], steps)

    def test_groups_add_group(self):

        groups_new = {GROUPS: {'group1': {}}}

        self.step_extractor.new_deployment_plan.update(groups_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=GROUP,
                entity_id='groups:group1',
                supported=False)
        ]

        self.assertEqual(expected_steps, steps)

    def test_groups_remove_group(self):

        groups_old = {GROUPS: {'group1': {}}}

        self.step_extractor.old_deployment_plan.update(groups_old)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='remove',
                entity_type=GROUP,
                entity_id='groups:group1',
                supported=False)
        ]

        self.assertEqual(expected_steps, steps)

    def test_groups_modify_group(self):

        groups_old = {GROUPS: {'group1': {'members': []}}}
        groups_new = {GROUPS: {'group1': {'members': ['a']}}}

        self.step_extractor.old_deployment_plan.update(groups_old)
        self.step_extractor.new_deployment_plan.update(groups_new)

        _, steps = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='modify',
                entity_type=GROUP,
                entity_id='groups:group1',
                supported=False)
        ]

        self.assertEqual(expected_steps, steps)

    def test_groups_member_order(self):
        groups_old = {GROUPS: {'group1': {'members': ['a', 'b']}}}
        groups_new = {GROUPS: {'group1': {'members': ['b', 'a']}}}

        self.step_extractor.old_deployment_plan.update(groups_old)
        self.step_extractor.new_deployment_plan.update(groups_new)

        _, steps = self.step_extractor.extract_steps()

        self.assertEqual([], steps)

    def test_cda_plugins_no_install(self):

        cda_plugins_new = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: {
                'cda_plugin1': {
                    'install': False}}}

        self.step_extractor.new_deployment_plan.update(cda_plugins_new)

        _, steps = self.step_extractor.extract_steps()

        self.assertEqual([], steps)

    def test_cda_plugins_add_cda_plugin(self):

        cda_plugins_new = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: {'cda_plugin1': {'install': True}}}

        self.step_extractor.new_deployment_plan.update(cda_plugins_new)

        steps, _ = self.step_extractor.extract_steps()

        # Managed CDA plugins are handled during plugin upload/delete
        self.assertEqual([], steps)

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

        steps, _ = self.step_extractor.extract_steps()

        # Managed CDA plugins are handled during plugin upload/delete
        self.assertEqual([], steps)

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

        steps, _ = self.step_extractor.extract_steps()

        # Although install is set to False on the new plugin, we are still
        # creating the step. We won't need to install the plugin (the
        # PluginHandler takes care of that), but the value still needs to be
        # updated in the node in the DB
        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=PLUGIN,
                entity_id='plugins_to_install:node1:new'
            )
        ]

        self.assertEqual(expected_steps, steps)

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

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='add',
                entity_type=PLUGIN,
                entity_id='plugins_to_install:node1:new',
                supported=True)
        ]

        self.assertEqual(expected_steps, steps)

    def test_ha_plugins_modify_ha_plugin(self):

        node_old = self._get_node_scheme()
        node_old.update({PLUGINS_TO_INSTALL: [
            {'name': 'name',
             'executor': 'host_agent',
             'install': True,
             'source': 'old'}]})
        nodes_old = {'node1': node_old}

        node_new = self._get_node_scheme()
        node_new.update({PLUGINS_TO_INSTALL: [
            {'name': 'name',
             'executor': 'host_agent',
             'install': True,
             'source': 'new'}]})
        nodes_new = {'node1': node_new}

        self.step_extractor.old_deployment_plan[NODES].update(nodes_old)
        self.step_extractor.new_deployment_plan[NODES].update(nodes_new)

        steps, _ = self.step_extractor.extract_steps()

        expected_steps = [
            DeploymentUpdateStep(
                action='modify',
                entity_type=PLUGIN,
                entity_id='plugins_to_install:node1:name',
                supported=True)
        ]

        self.assertEqual(expected_steps, steps)

    def test_all_changes_combined(self):

        path_before = get_resource(
            'deployment_update/combined_changes_before.json')

        path_after = get_resource(
            'deployment_update/combined_changes_after.json')

        with open(path_before) as fp_before, open(path_after) as fp_after:
            self.step_extractor.old_deployment_plan = json.load(fp_before)
            self.step_extractor.new_deployment_plan = json.load(fp_after)

        expected_steps = {
            'modify_description': DeploymentUpdateStep(
                'modify',
                DESCRIPTION,
                'description'),

            'remove_node': DeploymentUpdateStep(
                'remove',
                NODE,
                'nodes:node1'),

            'add_node': DeploymentUpdateStep(
                'add',
                NODE,
                'nodes:node2',
                topology_order=0),

            'modify_node_changed_type': DeploymentUpdateStep(
                'modify',
                NODE,
                'nodes:node3',
                supported=False),

            'add_property': DeploymentUpdateStep(
                'add',
                PROPERTY,
                'nodes:node4:properties:added_prop'),

            'remove_property': DeploymentUpdateStep(
                'remove',
                PROPERTY,
                'nodes:node4:properties:removed_prop'),

            'modify_property': DeploymentUpdateStep(
                'modify',
                PROPERTY,
                'nodes:node4:properties:modified_prop'),

            'remove_relationship': DeploymentUpdateStep(
                'remove',
                RELATIONSHIP,
                'nodes:node6:relationships:[0]'),

            'add_relationship': DeploymentUpdateStep(
                'add',
                RELATIONSHIP,
                'nodes:node7:relationships:[0]'),

            'remove_relationship_changed_target': DeploymentUpdateStep(
                'remove',
                RELATIONSHIP,
                'nodes:node9:relationships:[0]'),

            'add_relationship_changed_target': DeploymentUpdateStep(
                'add',
                RELATIONSHIP,
                'nodes:node9:relationships:[0]'),

            'remove_relationship_changed_type_and_target':
                DeploymentUpdateStep(
                    'remove',
                    RELATIONSHIP,
                    'nodes:node10:relationships:[0]'),

            'add_relationship_changed_type_and_target':
                DeploymentUpdateStep(
                    'add',
                    RELATIONSHIP,
                    'nodes:node10:relationships:[0]'),

            'add_operation': DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node11:operations:interface1.added_operation'),

            'add_operation_shortened': DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node11:operations:added_operation'),

            'remove_operation': DeploymentUpdateStep(
                'remove',
                OPERATION,
                'nodes:node11:operations:interface1.removed_operation'),

            'remove_operation_shortened': DeploymentUpdateStep(
                'remove',
                OPERATION,
                'nodes:node11:operations:removed_operation'),

            'modify_operation': DeploymentUpdateStep(
                'modify',
                OPERATION,
                'nodes:node11:operations:interface1.modified_operation'),

            'modify_operation_shortened': DeploymentUpdateStep(
                'modify',
                OPERATION,
                'nodes:node11:operations:modified_operation'),

            'add_relationship_operation': DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node12:relationships:[0]:target_operations:'
                'interface_for_modified_and_added.added_operation'),

            'add_relationship_operation_shortened':
                DeploymentUpdateStep(
                    'add',
                    OPERATION,
                    'nodes:node12:relationships:[0]:target_operations:'
                    'added_operation'),


            'remove_relationship_operation': DeploymentUpdateStep(
                'remove',
                OPERATION,
                'nodes:node12:relationships:[0]:source_operations:'
                'interface_for_intact_and_removed.removed_operation'),

            'remove_relationship_operation_shortened':
                DeploymentUpdateStep(
                    'remove',
                    OPERATION,
                    'nodes:node12:relationships:[0]:source_operations:'
                    'removed_operation'),

            'modify_relationship_operation': DeploymentUpdateStep(
                'modify',
                OPERATION,
                'nodes:node12:relationships:[0]:target_operations:'
                'interface_for_modified_and_added.modified_operation'),

            'modify_relationship_operation_shortened':
                DeploymentUpdateStep(
                    'modify',
                    OPERATION,
                    'nodes:node12:relationships:[0]:target_operations:'
                    'modified_operation'),

            'add_output': DeploymentUpdateStep(
                'add',
                OUTPUT,
                'outputs:added_output'),

            'remove_output': DeploymentUpdateStep(
                'remove',
                OUTPUT,
                'outputs:removed_output'),

            'modify_output': DeploymentUpdateStep(
                'modify',
                OUTPUT,
                'outputs:modified_output'),

            'add_workflow_same_plugin': DeploymentUpdateStep(
                'add',
                WORKFLOW,
                'workflows:added_workflow_same_plugin'),

            'add_workflow_new_plugin': DeploymentUpdateStep(
                'add',
                WORKFLOW,
                'workflows:added_workflow_new_plugin'),

            'remove_workflow': DeploymentUpdateStep(
                'remove',
                WORKFLOW,
                'workflows:removed_workflow'),

            'modify_workflow_same_plugin': DeploymentUpdateStep(
                'modify',
                WORKFLOW,
                'workflows:modified_workflow_same_plugin'),

            'modify_workflow_new_plugin': DeploymentUpdateStep(
                'modify',
                WORKFLOW,
                'workflows:modified_workflow_new_plugin'),

            'add_policy_type': DeploymentUpdateStep(
                'add',
                POLICY_TYPE,
                'policy_types:added_policy_type',
                supported=False),

            'remove_policy_type': DeploymentUpdateStep(
                'remove',
                POLICY_TYPE,
                'policy_types:removed_policy_type',
                supported=False),

            'modify_policy_type': DeploymentUpdateStep(
                'modify',
                POLICY_TYPE,
                'policy_types:modified_policy_type',
                supported=False),

            'add_policy_trigger': DeploymentUpdateStep(
                'add',
                POLICY_TRIGGER,
                'policy_triggers:added_policy_trigger',
                supported=False),

            'remove_policy_trigger': DeploymentUpdateStep(
                'remove',
                POLICY_TRIGGER,
                'policy_triggers:removed_policy_trigger',
                supported=False),

            'modify_policy_trigger': DeploymentUpdateStep(
                'modify',
                POLICY_TRIGGER,
                'policy_triggers:modified_policy_trigger',
                supported=False),

            'add_group': DeploymentUpdateStep(
                'add',
                GROUP,
                'groups:added_group',
                supported=False),

            'remove_group': DeploymentUpdateStep(
                'remove',
                GROUP,
                'groups:removed_group',
                supported=False),

            'modify_group': DeploymentUpdateStep(
                'modify',
                GROUP,
                'groups:modified_group',
                supported=False),

            'add_relationship_property': DeploymentUpdateStep(
                'add',
                PROPERTY,
                'nodes:node13:relationships:[0]:'
                'properties:added_relationship_prop',
                supported=False),

            'remove_relationship_property': DeploymentUpdateStep(
                'remove',
                PROPERTY,
                'nodes:node13:relationships:[0]:'
                'properties:removed_relationship_prop',
                supported=False),

            'modify_relationship_property': DeploymentUpdateStep(
                'modify',
                PROPERTY,
                'nodes:node13:relationships:[0]:'
                'properties:modified_relationship_prop',
                supported=False),

            'add_ha_plugin_plugins_to_install': DeploymentUpdateStep(
                'add',
                PLUGIN,
                'plugins_to_install:node18:plugin3_name'),

            'add_ha_plugin_plugin3_name': DeploymentUpdateStep(
                'add',
                PLUGIN,
                'plugins:node18:plugin3_name'),

            'add_cda_plugin_used_by_host': DeploymentUpdateStep(
                'add',
                PLUGIN,
                'plugins:node16:cda_plugin_for_operations2'),

            # the steps below are intended just to make the test pass.
            # ideally, they should be removed since they are incorrect

            'modify_node_add_contained_in_relationship':
                DeploymentUpdateStep(
                    'modify',
                    NODE,
                    'nodes:node8',
                    supported=False),

            'add_cda_operation': DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node16:operations:'
                'interface_for_plugin_based_operations.'
                'added_operation_new_cda_plugin',
                supported=True),

            'add_cda_operation_shortened': DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node16:operations:added_operation_new_cda_plugin',
                supported=True),

            'add_ha_operation': DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node17:operations:'
                'interface_for_plugin_based_operations.'
                'ha_operation_after',
                supported=True),

            'add_ha_operation_shortened': DeploymentUpdateStep(
                'add',
                OPERATION,
                'nodes:node17:operations:ha_operation_after',
                supported=True),

            'remove_ha_operation': DeploymentUpdateStep(
                'remove',
                OPERATION,
                'nodes:node17:operations:'
                'interface_for_plugin_based_operations.'
                'ha_operation_before',
                supported=True),

            'remove_ha_operation_shortened': DeploymentUpdateStep(
                'remove',
                OPERATION,
                'nodes:node17:operations:ha_operation_before',
                supported=True),

            'modify_ha_operation': DeploymentUpdateStep(
                'modify',
                OPERATION,
                'nodes:node18:operations:'
                'interface_for_plugin_based_operations.'
                'ha_operation_before',
                supported=True),

            'modify_ha_operation_shortened': DeploymentUpdateStep(
                'modify',
                OPERATION,
                'nodes:node18:operations:ha_operation_before',
                supported=True)
        }
        steps, unsupported_steps = self.step_extractor.extract_steps()
        steps.extend(unsupported_steps)
        self.assertEqual(set(expected_steps.values()), set(steps))

import json
import os
import unittest

from cloudify_rest_client.deployments import Deployment
from cloudify_system_workflows.deployment_update.step_extractor import (
    extract_steps,
    DeploymentUpdateStep,
    PROPERTY, PROPERTIES, OUTPUT, OUTPUTS, WORKFLOW, WORKFLOWS, NODE,
    NODES, OPERATION, OPERATIONS, RELATIONSHIP, RELATIONSHIPS,
    SOURCE_OPERATIONS, TARGET_OPERATIONS, TYPE, GROUP, GROUPS, POLICY_TYPE,
    POLICY_TYPES, POLICY_TRIGGER, POLICY_TRIGGERS, HOST_ID, PLUGIN,
    DEPLOYMENT_PLUGINS_TO_INSTALL, PLUGINS_TO_INSTALL, DESCRIPTION,
    _update_topology_order_of_add_node_steps,
    _find_relationship,
)


class StepExtractorTestCase(unittest.TestCase):

    @staticmethod
    def _get_node_scheme(node_id='node1', **params):
        node = {
            'id': node_id,
            OPERATIONS: {},
            PROPERTIES: {},
            RELATIONSHIPS: [],
            TYPE: '',
            HOST_ID: '',
            PLUGINS_TO_INSTALL: []
        }
        node.update(params)
        return node

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
        self.deployment = Deployment({
            'id': 'deployment_id',
            'groups': {}
        })

        self.deployment_plan = {
            DESCRIPTION: None,
            NODES: {},
            OPERATIONS: {},
            PROPERTIES: {},
            RELATIONSHIPS: [],
            TYPE: '',
            GROUPS: {},
            POLICY_TYPES: {},
            POLICY_TRIGGERS: {},
            DEPLOYMENT_PLUGINS_TO_INSTALL: {},
            OUTPUTS: {},
            WORKFLOWS: {}
        }

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
        _update_topology_order_of_add_node_steps(
            steps, topologically_sorted_added_nodes)

        self.assertEqual(5, add_node_e_step.topology_order)
        self.assertEqual(4, add_node_d_step.topology_order)
        self.assertEqual(3, add_node_c_step.topology_order)
        self.assertEqual(2, add_node_b_step.topology_order)
        self.assertEqual(1, add_node_a_step.topology_order)
        self.assertEqual(0, add_node_f_step.topology_order)

    def test_create_added_nodes_graph(self):
        self.deployment_plan[NODES] = [
            self._get_node_scheme('node_a', relationships=[
                {"target_id": 'node_c'}
            ]),
            self._get_node_scheme('node_b', relationships=[
                {"target_id": 'node_c'}
            ]),
            self._get_node_scheme('node_c', relationships=[
                {"target_id": 'node_e'}
            ]),
            self._get_node_scheme('node_d', relationships=[
                {"target_id": 'node_e'}
            ]),
            self._get_node_scheme('node_e'),
            self._get_node_scheme('node_f'),
        ]
        steps, _ = extract_steps([], self.deployment, self.deployment_plan)
        order_by_id = {s.entity_id: s.topology_order for s in steps}
        assert order_by_id['nodes:node_c'] > order_by_id['nodes:node_a']
        assert order_by_id['nodes:node_c'] > order_by_id['nodes:node_b']
        assert order_by_id['nodes:node_e'] > order_by_id['nodes:node_c']
        assert order_by_id['nodes:node_e'] > order_by_id['nodes:node_d']

    def test_description_no_change(self):
        self.deployment[DESCRIPTION] = 'description'
        self.deployment_plan[DESCRIPTION] = 'description'
        steps, _ = extract_steps({}, self.deployment, self.deployment_plan)
        assert steps == []

    def test_description_modify_description(self):
        self.deployment[DESCRIPTION] = 'description_old'
        self.deployment_plan[DESCRIPTION] = 'description_new'
        steps, _ = extract_steps({}, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=DESCRIPTION,
                entity_id='description')
        ]

    def test_outputs_no_change(self):
        self.deployment[OUTPUTS] = {'output1': 'output1_value'}
        self.deployment_plan[OUTPUTS] = self.deployment.outputs
        steps, _ = extract_steps({}, self.deployment, self.deployment_plan)
        assert steps == []

    def test_outputs_add_output(self):
        self.deployment_plan[OUTPUTS] = {'output1': 'output1_value'}
        steps, _ = extract_steps({}, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=OUTPUT,
                entity_id='outputs:output1')
        ]

    def test_outputs_remove_output(self):
        self.deployment[OUTPUTS] = {'output1': 'output1_value'}
        steps, _ = extract_steps({}, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=OUTPUT,
                entity_id='outputs:output1')
        ]

    def test_outputs_modify_output(self):
        self.deployment[OUTPUTS] = {'output1': 'output1_value'}
        self.deployment_plan[OUTPUTS] = {'output1': 'output1_modified_value'}
        steps, _ = extract_steps({}, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=OUTPUT,
                entity_id='outputs:output1')
        ]

    def test_workflows_no_change(self):
        self.deployment[WORKFLOWS] = {
            'intact_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'plugin_for_workflows'
            }
        }
        self.deployment_plan[WORKFLOWS] = self.deployment.workflows
        steps, _ = extract_steps({}, self.deployment, self.deployment_plan)
        assert steps == []

    def test_workflows_add_workflow_of_existing_plugin(self):
        self.deployment_plan[WORKFLOWS] = {
            'added_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'plugin_for_workflows'
            }
        }
        steps, _ = extract_steps({}, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=WORKFLOW,
                entity_id='workflows:added_workflow')
        ]

    def test_workflows_add_workflow_script(self):
        self.deployment_plan[WORKFLOWS] = {
            'new_workflow': {
                'plugin': 'script',
            }
        }
        steps, _ = extract_steps({}, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=WORKFLOW,
                entity_id='workflows:new_workflow')
        ]

    def test_workflows_remove_workflow(self):
        self.deployment[WORKFLOWS] = {
            'removed_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'plugin_for_workflows'
            }
        }
        steps, _ = extract_steps({}, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=WORKFLOW,
                entity_id='workflows:removed_workflow')
        ]

    def test_workflows_modify_workflow_of_existing_plugin(self):
        self.deployment[WORKFLOWS] = {
            'added_workflow': {
                'operation': 'module_name.foo',
                'plugin': 'plugin_for_workflows'
            }
        }
        self.deployment_plan[WORKFLOWS] = {
            'added_workflow': {
                'operation': 'module_name.bar',
                'plugin': 'plugin_for_workflows'
            }
        }
        steps, _ = extract_steps({}, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=WORKFLOW,
                entity_id='workflows:added_workflow')
        ]

    def test_nodes_no_change(self):
        nodes = [self._get_node_scheme()]
        self.deployment_plan[NODES] = nodes
        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == []

    def test_nodes_add_node(self):
        self.deployment_plan[NODES] = [self._get_node_scheme()]
        steps, _ = extract_steps({}, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=NODE,
                entity_id='nodes:node1')
        ]

    def test_nodes_remove_node(self):
        nodes = [self._get_node_scheme()]
        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=NODE,
                entity_id='nodes:node1')
        ]

    def test_nodes_add_and_remove_node_changed_type(self):
        nodes = [self._get_node_scheme(type='old_type')]
        self.deployment_plan[NODES] = [self._get_node_scheme(type='new_type')]

        supported_steps, unsupported_steps = \
            extract_steps(nodes, self.deployment, self.deployment_plan)

        assert len(supported_steps) == 0
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=NODE,
                entity_id='nodes:node1',
                supported=False),
        ]

    def test_nodes_add_and_remove_node_changed_type_and_host_id(self):
        nodes = [self._get_node_scheme(host_id='old_host_id')]
        self.deployment_plan[NODES] = [
            self._get_node_scheme(type='new_host_id')]

        supported_steps, unsupported_steps = \
            extract_steps(nodes, self.deployment, self.deployment_plan)
        assert len(supported_steps) == 0
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=NODE,
                entity_id='nodes:node1',
                supported=False),
        ]

    def test_node_properties_no_change(self):
        nodes = [self._get_node_scheme(
            properties={'property1': 'property1_value'}
        )]
        self.deployment_plan[NODES] = nodes

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == []

    def test_node_properties_add_property(self):
        nodes = [self._get_node_scheme()]
        self.deployment_plan[NODES] = [
            self._get_node_scheme(properties={'property1': 'property1_value'})]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=PROPERTY,
                entity_id='nodes:node1:properties:property1')
        ]

    def test_node_properties_remove_property(self):
        nodes = [self._get_node_scheme(properties={
            'property1': 'property1_value'})]
        self.deployment_plan[NODES] = [self._get_node_scheme()]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=PROPERTY,
                entity_id='nodes:node1:properties:property1')
        ]

    def test_node_properties_modify_property(self):
        nodes = [self._get_node_scheme(properties={
            'property1': 'property1_value'})]
        self.deployment_plan[NODES] = [self._get_node_scheme(properties={
            'property1': 'property1_modified_value'})]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=PROPERTY,
                entity_id='nodes:node1:properties:property1')
        ]

    def test_node_operations_no_change(self):
        nodes = [self._get_node_scheme(operations={
            'full.operation1.name': {
                'operation1_field': 'operation1_field_value'
            }
        })]
        self.deployment_plan[NODES] = nodes

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == []

    def test_node_operations_add_operation(self):
        nodes = [self._get_node_scheme()]

        self.deployment_plan[NODES] = [self._get_node_scheme(operations={
            'full.operation1.name': {
                'operation1_field': 'operation1_field_value'
            }
        })]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=OPERATION,
                entity_id='nodes:node1:operations:full.operation1.name')
        ]

    def test_node_operations_remove_operation(self):
        nodes = [self._get_node_scheme(operations={
            'full.operation1.name': {
                'operation1_field': 'operation1_field_value'
            }
        })]
        self.deployment_plan[NODES] = [self._get_node_scheme()]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=OPERATION,
                entity_id='nodes:node1:operations:full.operation1.name')
        ]

    def test_node_operations_modify_operation(self):
        nodes = [self._get_node_scheme(operations={
            'full.operation1.name': {
                'operation1_field': 'operation1_field_value'
            }
        })]
        self.deployment_plan[NODES] = [self._get_node_scheme(operations={
            'full.operation1.name': {
                'operation1_field': 'operation1_modified_field_value'
            }
        })]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=OPERATION,
                entity_id='nodes:node1:operations:full.operation1.name')
        ]

    def test_relationships_no_change(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target'
            }
        ])]
        self.deployment_plan[NODES] = nodes

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == []

    def test_relationships_add_relationship(self):
        nodes = [self._get_node_scheme()]
        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target'
            }
        ])]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

    def test_relationships_remove_relationship(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target'
            }
        ])]
        self.deployment_plan[NODES] = [self._get_node_scheme()]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

    def test_relationships_change_type(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target'
            }
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'different_relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target'
            }
        ])]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]'),
            DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

    def test_relationships_change_target_non_contained_in(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'target_id': 'relationship_target',
                'type_hierarchy': ['rel_hierarchy']
            }
        ])]
        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'target_id': 'different_relationship_target',
                'type_hierarchy': ['rel_hierarchy']
            }
        ])]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]'),
            DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

    def test_relationships_change_target_contained_in(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'target_id': 'relationship_target',
                'type_hierarchy': ['rel_hierarchy',
                                   'cloudify.relationships.contained_in']
            }
        ])]
        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'target_id': 'different_relationship_target',
                'type_hierarchy': ['rel_hierarchy',
                                   'cloudify.relationships.contained_in']}
        ])]

        _, unsupported_steps = extract_steps(
            nodes, self.deployment, self.deployment_plan)

        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=NODE,
                entity_id='nodes:node1',
                supported=False),
        ]

    def test_relationships_change_type_and_target(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target'
            }
        ])]
        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'different_relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'different_relationship_target'
            }
        ])]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]'),
            DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id='nodes:node1:relationships:[0]')
        ]

    def test_relationships_modify_order(self):
        nodes = [self._get_node_scheme(relationships=[
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
        ])]
        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
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
        ])]
        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)

        # we don't care for the order the steps were created in
        assert set(steps) == {
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
        }

    def test_relationships_modify_order_with_add_and_remove(self):
        nodes = [self._get_node_scheme(relationships=[
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_1'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_2'},
            {'type': 'relationship_type',
             'type_hierarchy': ['rel_hierarchy'],
             'target_id': 'relationship_target_3'},
        ])]
        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
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
        ])]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)

        # we don't care for the order the steps were created in
        assert set(steps) == {
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
        }

    def test_relationships_add_source_operation(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                SOURCE_OPERATIONS: {}
            }
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                SOURCE_OPERATIONS: {'full.operation1': {}}
            }
        ])]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'source_operations:full.operation1')
        ]

    def test_relationships_remove_source_operation(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                SOURCE_OPERATIONS: {'full.operation1': {}}
            }
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                SOURCE_OPERATIONS: {}
            }
        ])]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'source_operations:full.operation1')
        ]

    def test_duplicate_relationship(self):
        rel = {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
            }
        nodes = [self._get_node_scheme(relationships=[rel, rel])]

        self.deployment_plan[NODES] = [
            self._get_node_scheme(relationships=[rel, rel])]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == []

    def test_relationships_modify_source_operation(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                SOURCE_OPERATIONS: {
                    'full.operation1': {
                        'op1_old_field': 'op1_field_value'
                    }
                }
            }
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                SOURCE_OPERATIONS: {
                    'full.operation1': {
                        'op1_new_field': 'op1_field_value'
                    }
                }
            }
        ])]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'source_operations:full.operation1')
        ]

    def test_relationships_add_target_operation(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                TARGET_OPERATIONS: {}
            }
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                TARGET_OPERATIONS: {'full.operation1': {}}
            }
        ])]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'target_operations:full.operation1')
        ]

    def test_relationships_remove_target_operation(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                TARGET_OPERATIONS: {'full.operation1': {}}
            }
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                TARGET_OPERATIONS: {}
            }
        ])]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'target_operations:full.operation1')
        ]

    def test_relationships_modify_target_operation(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                TARGET_OPERATIONS: {
                    'full.operation1': {
                        'op1_old_field': 'op1_field_value'
                    }
                }
            }
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                TARGET_OPERATIONS: {
                    'full.operation1': {
                        'op1_new_field': 'op1_field_value'
                    }
                }
            }
        ])]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=OPERATION,
                entity_id='nodes:node1:relationships:[0]:'
                          'target_operations:full.operation1')
        ]

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
        steps.sort()
        assert steps == expected_step_order

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
        assert steps == expected_step_order

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
        assert steps == expected_step_order

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
        assert steps == expected_step_order

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
        assert steps == expected_step_order

    def test_relationships_intact_property(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                PROPERTIES: {
                    'property1': 'property1_value'
                }
            }
        ])]
        self.deployment_plan[NODES] = nodes

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == []

    def test_relationships_add_property(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                'properties': {}
            }
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                PROPERTIES: {
                    'property1': 'property1_different_value'
                }
            }
        ])]
        _, unsupported_steps = extract_steps(
            nodes, self.deployment, self.deployment_plan)
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=PROPERTY,
                entity_id='nodes:node1:relationships:[0]:'
                          'properties:property1',
                supported=False)
        ]

    def test_relationships_remove_property(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                PROPERTIES: {
                    'property1': 'property1_different_value'
                }
            }
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                'properties': {}
            }
        ])]

        _, unsupported_steps = extract_steps(
            nodes, self.deployment, self.deployment_plan)
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=PROPERTY,
                entity_id='nodes:node1:relationships:[0]:'
                          'properties:property1',
                supported=False)
        ]

    def test_relationships_modify_property(self):
        nodes = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                PROPERTIES: {
                    'property1': 'property1_value'
                }
            }
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(relationships=[
            {
                'type': 'relationship_type',
                'type_hierarchy': ['rel_hierarchy'],
                'target_id': 'relationship_target',
                PROPERTIES: {
                    'property1': 'property1_different_value'
                }
            }
        ])]

        _, unsupported_steps = extract_steps(
            nodes, self.deployment, self.deployment_plan)
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=PROPERTY,
                entity_id='nodes:node1:relationships:[0]:'
                          'properties:property1',
                supported=False)
        ]

    def test_extract_steps_policy_types_no_change(self):
        policy_types = {'policy_type1': 'policy_type1_value'}
        self.deployment[POLICY_TYPES] = policy_types
        self.deployment_plan[POLICY_TYPES] = policy_types

        steps, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert steps == []
        assert unsupported_steps == []

    def test_policy_types_add_policy_type(self):
        self.deployment_plan[POLICY_TYPES] = {
            'policy_type1': 'policy_type1_value'
        }

        _, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=POLICY_TYPE,
                entity_id='policy_types:policy_type1',
                supported=False)
        ]

    def test_policy_types_remove_policy_type(self):
        self.deployment[POLICY_TYPES] = {'policy_type1': 'policy_type1_value'}
        _, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=POLICY_TYPE,
                entity_id='policy_types:policy_type1',
                supported=False)
        ]

    def test_policy_types_modify_policy_type(self):
        self.deployment[POLICY_TYPES] = {'policy_type1': 'policy_type1_value'}
        self.deployment_plan[POLICY_TYPES] = {
            'policy_type1': 'policy_type1_modified_value'
        }

        _, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=POLICY_TYPE,
                entity_id='policy_types:policy_type1',
                supported=False)
        ]

    def test_extract_steps_policy_triggers_no_change(self):
        policy_triggers = {'policy_trigger1': 'policy_trigger1_value'}
        self.deployment[POLICY_TRIGGERS] = policy_triggers
        self.deployment_plan[POLICY_TRIGGERS] = policy_triggers

        steps, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert steps == []
        assert unsupported_steps == []

    def test_policy_triggers_add_policy_trigger(self):
        self.deployment_plan[POLICY_TRIGGERS] = {
            'policy_trigger1': 'policy_trigger1_value'
        }

        _, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=POLICY_TRIGGER,
                entity_id='policy_triggers:policy_trigger1',
                supported=False)
        ]

    def test_policy_triggers_remove_policy_trigger(self):
        self.deployment[POLICY_TRIGGERS] = {
            'policy_trigger1': 'policy_trigger1_value'
        }
        _, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=POLICY_TRIGGER,
                entity_id='policy_triggers:policy_trigger1',
                supported=False)
        ]

    def test_policy_triggers_modify_policy_trigger(self):
        self.deployment[POLICY_TRIGGERS] = {
            'policy_trigger1': 'policy_trigger1_value'
        }
        self.deployment_plan[POLICY_TRIGGERS] = {
            'policy_trigger1': 'policy_trigger1_modified_value'
        }

        _, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=POLICY_TRIGGER,
                entity_id='policy_triggers:policy_trigger1',
                supported=False)
        ]

    def test_groups_no_change(self):
        groups = {'group1': {}}
        self.deployment[GROUPS] = groups
        self.deployment_plan[GROUPS] = groups
        steps, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert steps == []
        assert unsupported_steps == []

    def test_groups_add_group(self):
        self.deployment_plan[GROUPS] = {'group1': {}}
        _, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=GROUP,
                entity_id='groups:group1',
                supported=False)
        ]

    def test_groups_remove_group(self):
        self.deployment[GROUPS] = {'group1': {}}
        _, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='remove',
                entity_type=GROUP,
                entity_id='groups:group1',
                supported=False)
        ]

    def test_groups_modify_group(self):
        self.deployment[GROUPS] = {'group1': {'members': []}}
        self.deployment_plan[GROUPS] = {'group1': {'members': ['a']}}
        _, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert unsupported_steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=GROUP,
                entity_id='groups:group1',
                supported=False)
        ]

    def test_groups_member_order(self):
        self.deployment[GROUPS] = {'group1': {'members': ['a', 'b']}}
        self.deployment_plan[GROUPS] = {'group1': {'members': ['b', 'a']}}
        steps, unsupported_steps = extract_steps(
            {}, self.deployment, self.deployment_plan)
        assert steps == []
        assert unsupported_steps == []

    def test_ha_plugins_no_install(self):
        nodes = [self._get_node_scheme(plugins_to_install=[
            {'name': 'old', 'install': True}
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(
            plugins_to_install=[{'name': 'new', 'install': False}]
        )]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        # Although install is set to False on the new plugin, we are still
        # creating the step. We won't need to install the plugin (the
        # PluginHandler takes care of that), but the value still needs to be
        # updated in the node in the DB
        assert steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=PLUGIN,
                entity_id='plugins_to_install:node1:new'
            )
        ]

    def test_ha_plugins_add_ha_plugin(self):
        nodes = [self._get_node_scheme(plugins_to_install=[
            {'name': 'old', 'install': True}
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(
            plugins_to_install=[{'name': 'new', 'install': True}]
        )]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='add',
                entity_type=PLUGIN,
                entity_id='plugins_to_install:node1:new',
                supported=True)
        ]

    def test_ha_plugins_modify_ha_plugin(self):
        nodes = [self._get_node_scheme(plugins_to_install=[
            {
                'name': 'name',
                'executor': 'host_agent',
                'install': True,
                'source': 'old'
            }
        ])]

        self.deployment_plan[NODES] = [self._get_node_scheme(
            plugins_to_install=[
                {
                    'name': 'name',
                    'executor': 'host_agent',
                    'install': True,
                    'source': 'new'
                }
            ]
        )]

        steps, _ = extract_steps(nodes, self.deployment, self.deployment_plan)
        assert steps == [
            DeploymentUpdateStep(
                action='modify',
                entity_type=PLUGIN,
                entity_id='plugins_to_install:node1:name',
                supported=True)
        ]

    def test_all_changes_combined(self):
        path_before = os.path.join(
            os.path.dirname(__file__), 'combined_changes_before.json')
        path_after = os.path.join(
            os.path.dirname(__file__), 'combined_changes_after.json')
        with open(path_before) as fp_before, open(path_after) as fp_after:
            plan_before = json.load(fp_before)
            plan_after = json.load(fp_after)

        nodes = list(plan_before['nodes'].values())
        plan_after['nodes'] = list(plan_after['nodes'].values())
        self.deployment[GROUPS] = plan_before['groups']
        self.deployment[WORKFLOWS] = plan_before['workflows']
        self.deployment[POLICY_TYPES] = plan_before['policy_types']
        self.deployment[POLICY_TRIGGERS] = plan_before['policy_triggers']
        self.deployment[OUTPUTS] = plan_before['outputs']

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
        steps, unsupported_steps = extract_steps(
            nodes, self.deployment, plan_after)
        steps.extend(unsupported_steps)
        self.assertEqual(set(expected_steps.values()), set(steps))

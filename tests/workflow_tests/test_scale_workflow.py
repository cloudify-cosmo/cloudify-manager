########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.


from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import execute_workflow


class TestScaleWorkflow(TestCase):

    def test_compute_scale_out_compute(self):
        expectations = self.deploy('scale1')
        expectations['compute']['new']['install'] = 1
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute'})
        expectations['compute']['new']['install'] = 1
        expectations['compute']['existing']['install'] = 1
        self.deployment_assertions(expectations)

    def test_compute_scale_in_compute(self):
        expectations = self.deploy('scale4')
        expectations['compute']['new']['install'] = 3
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': -1})
        expectations['compute']['existing']['install'] = 2
        expectations['compute']['removed']['install'] = 1
        expectations['compute']['removed']['uninstall'] = 1
        self.deployment_assertions(expectations)

    def test_compute_scale_in_compute_ignore_failure_true(self):
        expectations = self.deploy('scale_ignore_failure')
        expectations['compute']['new']['install'] = 3
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'ignore_failure': True,
            'delta': -1})
        expectations['compute']['existing']['install'] = 2
        expectations['compute']['removed']['install'] = 1
        expectations['compute']['removed']['uninstall'] = 1
        self.deployment_assertions(expectations)

    def test_compute_scale_in_compute_ignore_failure_false(self):
        expectations = self.deploy('scale_ignore_failure')
        expectations['compute']['new']['install'] = 3
        self.deployment_assertions(expectations)

        try:
            self.scale(parameters={
                'scalable_entity_name': 'compute',
                'ignore_failure': False,
                'delta': -1})
        except RuntimeError as e:
            self.assertIn(
                "RuntimeError: Workflow failed: Task failed "
                "'testmockoperations.tasks.mock_stop_failure'",
                str(e))
        else:
            self.fail()

    def test_compute_scale_out_and_in_compute_from_0(self):
        expectations = self.deploy('scale10')
        expectations['compute']['new']['install'] = 0
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute'})
        expectations['compute']['new']['install'] = 1
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': -1})
        expectations['compute']['new']['install'] = 0
        expectations['compute']['existing']['install'] = 0
        expectations['compute']['removed']['install'] = 1
        expectations['compute']['removed']['uninstall'] = 1
        self.deployment_assertions(expectations)

    def test_compute_scale_out_2_compute(self):
        expectations = self.deploy('scale1')
        expectations['compute']['new']['install'] = 1
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': 2})
        expectations['compute']['new']['install'] = 2
        expectations['compute']['existing']['install'] = 1
        self.deployment_assertions(expectations)

    def test_compute_scale_in_2_compute(self):
        expectations = self.deploy('scale4')
        expectations['compute']['new']['install'] = 3
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': -2})
        expectations['compute']['existing']['install'] = 1
        expectations['compute']['removed']['install'] = 2
        expectations['compute']['removed']['uninstall'] = 2
        self.deployment_assertions(expectations)

    def test_db_contained_in_compute_scale_out_compute(self):
        expectations = self.deploy('scale2')
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute'})
        expectations['compute']['new']['install'] = 1
        expectations['compute']['existing']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        self.deployment_assertions(expectations)

    def test_db_contained_in_compute_scale_in_compute(self):
        expectations = self.deploy('scale5')
        expectations['compute']['new']['install'] = 2
        expectations['db']['new']['install'] = 4
        expectations['db']['new']['rel_install'] = 8
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': -1})
        expectations['compute']['existing']['install'] = 1
        expectations['compute']['removed']['install'] = 1
        expectations['compute']['removed']['uninstall'] = 1
        expectations['db']['existing']['install'] = 2
        expectations['db']['existing']['rel_install'] = 4
        expectations['db']['removed']['install'] = 2
        expectations['db']['removed']['uninstall'] = 2
        expectations['db']['removed']['rel_install'] = 4
        expectations['db']['removed']['rel_uninstall'] = 4
        self.deployment_assertions(expectations)

    def test_db_contained_in_compute_scale_out_db(self):
        expectations = self.deploy('scale2')
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'db',
            'scale_compute': True})
        expectations['compute']['new']['install'] = 1
        expectations['compute']['existing']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        self.deployment_assertions(expectations)

    def test_db_contained_in_compute_scale_in_db(self):
        expectations = self.deploy('scale5')
        expectations['compute']['new']['install'] = 2
        expectations['db']['new']['install'] = 4
        expectations['db']['new']['rel_install'] = 8
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'db',
            'delta': -1,
            'scale_compute': True})
        expectations['compute']['existing']['install'] = 1
        expectations['compute']['removed']['install'] = 1
        expectations['compute']['removed']['uninstall'] = 1
        expectations['db']['existing']['install'] = 2
        expectations['db']['existing']['rel_install'] = 4
        expectations['db']['removed']['install'] = 2
        expectations['db']['removed']['uninstall'] = 2
        expectations['db']['removed']['rel_install'] = 4
        expectations['db']['removed']['rel_uninstall'] = 4
        self.deployment_assertions(expectations)

    def test_db_contained_in_compute_scale_out_db_scale_db(self):
        expectations = self.deploy('scale2')
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'db',
            'scale_compute': False})
        expectations['compute']['existing']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        self.deployment_assertions(expectations)

    def test_db_contained_in_compute_scale_in_db_scale_db(self):
        expectations = self.deploy('scale5')
        expectations['compute']['new']['install'] = 2
        expectations['db']['new']['install'] = 4
        expectations['db']['new']['rel_install'] = 8
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'db',
            'delta': -1,
            'scale_compute': False})
        expectations['compute']['existing']['install'] = 2
        expectations['db']['existing']['install'] = 2
        expectations['db']['existing']['rel_install'] = 4
        expectations['db']['removed']['install'] = 2
        expectations['db']['removed']['uninstall'] = 2
        expectations['db']['removed']['rel_install'] = 4
        expectations['db']['removed']['rel_uninstall'] = 4
        self.deployment_assertions(expectations)

    def test_db_connected_to_compute_scale_out_compute(self):
        expectations = self.deploy('scale3')
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute'})
        expectations['compute']['new']['install'] = 1
        expectations['compute']['existing']['install'] = 1
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        expectations['db']['existing']['scale_rel_install'] = 2
        self.deployment_assertions(expectations)

    def test_db_connected_to_compute_scale_in_compute(self):
        expectations = self.deploy('scale6')
        expectations['compute']['new']['install'] = 2
        expectations['db']['new']['install'] = 2
        expectations['db']['new']['rel_install'] = 8
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': -1})
        expectations['compute']['existing']['install'] = 1
        expectations['compute']['removed']['install'] = 1
        expectations['compute']['removed']['uninstall'] = 1
        expectations['db']['existing']['install'] = 2
        expectations['db']['existing']['rel_install'] = 8
        expectations['db']['existing']['rel_uninstall'] = 4
        self.deployment_assertions(expectations)

    def test_db_connected_to_compute_scale_in_and_out_compute_from_0(self):
        expectations = self.deploy('scale11')
        expectations['compute']['new']['install'] = 0
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 0
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': 1})
        expectations['compute']['new']['install'] = 1
        expectations['compute']['existing']['install'] = 0
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 0
        expectations['db']['existing']['scale_rel_install'] = 2
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': -1})
        expectations['compute']['new']['install'] = 0
        expectations['compute']['existing']['install'] = 0
        expectations['compute']['removed']['install'] = 1
        expectations['compute']['removed']['uninstall'] = 1
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['scale_rel_install'] = 2
        expectations['db']['existing']['rel_uninstall'] = 2
        self.deployment_assertions(expectations)

    def test_db_connected_to_compute_scale_out_db(self):
        expectations = self.deploy('scale3')
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'db'})
        expectations['compute']['existing']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        self.deployment_assertions(expectations)

    def test_db_connected_to_compute_scale_in_db(self):
        expectations = self.deploy('scale6')
        expectations['compute']['new']['install'] = 2
        expectations['db']['new']['install'] = 2
        expectations['db']['new']['rel_install'] = 8
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'db',
            'delta': -1})
        expectations['compute']['existing']['install'] = 2
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 4
        expectations['db']['removed']['install'] = 1
        expectations['db']['removed']['uninstall'] = 1
        expectations['db']['removed']['rel_install'] = 4
        expectations['db']['removed']['rel_uninstall'] = 4
        self.deployment_assertions(expectations)

    def test_compute_scale_out_compute_rollback(self):
        fail_operations = [{
            'workflow': 'scale',
            'node': 'compute',
            'operation': 'cloudify.interfaces.lifecycle.start'
        }]

        expectations = self.deploy('scale7', inputs={'fail': fail_operations})
        expectations['compute']['new']['install'] = 1
        self.deployment_assertions(expectations)

        with self.assertRaises(RuntimeError) as e:
            self.scale(parameters={'scalable_entity_name': 'compute'})
        self.assertIn('TEST_EXPECTED_FAIL', str(e.exception))
        expectations = self.expectations()
        expectations['compute']['new']['install'] = 1
        expectations['compute']['new']['uninstall'] = 1
        expectations['compute']['existing']['install'] = 1
        self.deployment_assertions(expectations, rollback=True)

    def test_db_contained_in_compute_scale_out_compute_rollback(self):
        fail_operations = [{
            'workflow': 'scale',
            'node': 'db',
            'operation': 'cloudify.interfaces.lifecycle.start'
        }]

        expectations = self.deploy('scale8', inputs={'fail': fail_operations})
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        with self.assertRaises(RuntimeError) as e:
            self.scale(parameters={'scalable_entity_name': 'compute'})
        self.assertIn('TEST_EXPECTED_FAIL', str(e.exception))
        expectations = self.expectations()
        expectations['compute']['new']['install'] = 1
        expectations['compute']['new']['uninstall'] = 1
        expectations['compute']['existing']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        # this is somewhat of a hack. scale_rel_install only considers
        # establish, so we reuse this to decrease 2 from the expected establish
        # invocation, as start is the one that fails.
        # whoever you are that may be reading this. please don't hate me.
        # i mean no harm
        expectations['db']['new']['scale_rel_install'] = -2
        expectations['db']['new']['uninstall'] = 1
        expectations['db']['new']['rel_uninstall'] = 2
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        self.deployment_assertions(expectations, rollback=True)

    def test_db_connected_to_compute_scale_out_compute_rollback(self):
        fail_operations = [{
            'workflow': 'scale',
            'node': 'compute',
            'operation': 'cloudify.interfaces.lifecycle.start'
        }]

        expectations = self.deploy('scale9', inputs={'fail': fail_operations})
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        with self.assertRaises(RuntimeError) as e:
            self.scale(parameters={'scalable_entity_name': 'compute'})
        self.assertIn('TEST_EXPECTED_FAIL', str(e.exception))
        expectations = self.expectations()
        expectations['compute']['new']['install'] = 1
        expectations['compute']['new']['uninstall'] = 1
        expectations['compute']['existing']['install'] = 1
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        expectations['db']['existing']['rel_uninstall'] = 2
        self.deployment_assertions(expectations, rollback=True)

    def test_group_scale(self):
        node_ids = ['compute', 'webserver', 'db']

        def test_assertions(expected_node_count, assert_type):
            for node_id in node_ids:
                self.assertEqual(
                    expected_node_count,
                    len(self.client.node_instances.list(
                        self.deployment_id,
                        node_id=node_id).items)
                )
            plugin_name = 'testmockoperations'
            invocations = self.get_plugin_data(
                plugin_name,
                self.deployment_id).get('mock_operation_invocation', [])

            rel_ops = ['preconfigure', 'postconfigure', 'establish', 'unlink']
            lifecycle_install_ops = ['create', 'configure', 'start']
            lifecycle_install_ops_and_rel_ops = ['create',
                                                 'preconfigure',
                                                 'configure',
                                                 'postconfigure',
                                                 'start',
                                                 'establish']
            lifecycle_uninstall_ops = ['stop', 'delete']
            lifecycle_uninstall_ops_and_rel_ops = ['stop', 'unlink', 'delete']
            if assert_type in ['install', 'scale_out']:
                expected = [
                    ('compute', lifecycle_install_ops, None),
                    ('webserver', lifecycle_install_ops_and_rel_ops,
                     'compute'),
                    ('db', lifecycle_install_ops_and_rel_ops, 'webserver')]
            elif assert_type == 'scale_in':
                expected = [
                    ('db', lifecycle_uninstall_ops_and_rel_ops, 'webserver'),
                    ('webserver', lifecycle_uninstall_ops_and_rel_ops,
                     'compute'),
                    ('compute', lifecycle_uninstall_ops, None)]
            else:
                self.fail('Unsupported {0}'.format(assert_type))

            index = 0
            for expected_invocations in expected:
                node_id, operations, target_id = expected_invocations
                for operation in operations:
                    rel_op = operation in rel_ops
                    count = 2 if rel_op else 1
                    for _ in range(count):
                        invocation = invocations[index]
                        node_id_key = 'source' if rel_op else 'node'
                        self.assertEqual(node_id, invocation[node_id_key])
                        self.assertEqual(operation, invocation['operation'])
                        if rel_op:
                            self.assertEqual(target_id, invocation['target'])
                        index += 1

            self.clear_plugin_data(plugin_name)

        self.deploy('scale_groups')
        test_assertions(expected_node_count=1, assert_type='install')

        self.scale(parameters={'scalable_entity_name': 'group1', 'delta': 1})
        test_assertions(expected_node_count=2, assert_type='scale_out')

        self.scale(parameters={'scalable_entity_name': 'group1', 'delta': -1})
        test_assertions(expected_node_count=1, assert_type='scale_in')

    def setUp(self):
        super(TestScaleWorkflow, self).setUp()
        self.previous_ids = []
        self.previous_instances = []

    def deployment_assertions(self, expected, rollback=False):
        def expected_invocations(_expectations, num_instances):
            result = {}
            install_count = _expectations.get('install') or 0
            result.update({
                'create': install_count / num_instances,
                'configure': install_count / num_instances,
                'start': install_count / num_instances
            })
            uninstall_count = _expectations.get('uninstall') or 0
            result.update({
                'stop': uninstall_count / num_instances,
                'delete': uninstall_count / num_instances,
            })
            rel_install_count = _expectations.get('rel_install') or 0
            scale_rel_install_count = _expectations.get(
                'scale_rel_install') or 0
            result.update({
                'preconfigure': rel_install_count / num_instances,
                'postconfigure': rel_install_count / num_instances,
                'establish': (rel_install_count + scale_rel_install_count) /
                num_instances
            })
            rel_uninstall_count = _expectations.get('rel_uninstall') or 0
            result.update({
                'unlink': rel_uninstall_count / num_instances
            })
            return result

        if rollback:
            mod = self.client.deployment_modifications.list()[0]
            rolledback = [i for i in mod.node_instances.added_and_related if
                          i.get('modification') == 'added']
        else:
            rolledback = []

        instances = self.client.node_instances.list()
        instance_ids = [i.id for i in instances]

        calculated_expected = {}
        for node_id, expectations in expected.items():
            new_expectation = expectations['new']
            existing_expectation = expectations['existing']
            removed_expectation = expectations['removed']
            node_instances = [i for i in instances if i.node_id == node_id]
            node_rolledback = [i for i in rolledback if i.node_id == node_id]

            if rollback:
                new_instances = node_rolledback
            else:
                new_instances = [i for i in node_instances
                                 if i.id not in self.previous_ids]
            existing_instances = [i for i in node_instances
                                  if i.id in self.previous_ids]
            removed_instances = [i for i in self.previous_instances
                                 if i.id not in instance_ids and
                                 i.node_id == node_id]
            self.assertEqual(len(new_instances),
                             new_expectation.get('install') or 0,
                             'new_instances: {0}, install_expectations: {1}'
                             .format(new_instances,
                                     new_expectation.get('install')))
            self.assertEqual(len(existing_instances),
                             existing_expectation.get('install') or 0,
                             'existing_instances: {0}, '
                             'install_expectations: {1}'
                             .format(existing_instances,
                                     existing_expectation.get('install')))
            self.assertEqual(len(removed_instances),
                             removed_expectation.get('uninstall') or 0,
                             'removed_instances: {0}, '
                             'uninstall_expectations: {1}'
                             .format(removed_instances,
                                     removed_expectation.get('uninstall')))
            for new_instance in new_instances:
                calculated_expected.update({
                    new_instance.id: expected_invocations(
                        new_expectation, len(new_instances))})
            for existing_instance in existing_instances:
                calculated_expected.update({
                    existing_instance.id: expected_invocations(
                        existing_expectation, len(existing_instances))})
            for removed_instance in removed_instances:
                calculated_expected.update({
                    removed_instance.id: expected_invocations(
                        removed_expectation, len(removed_instances))})

        invocations = self.get_plugin_data(
            'testmockoperations', self.deployment_id
        ).get('mock_operation_invocation', [])
        total_expected_count = 0
        for instance_id, operations in calculated_expected.items():
            for operation, expected_count in operations.items():
                total_expected_count += expected_count
                op_invocations = [i for i in invocations
                                  if i['operation'] == operation and
                                  i['id'] == instance_id]
                self.assertEqual(expected_count, len(op_invocations),
                                 'expected_count: {0}, op_invocations: {1}'
                                 .format(expected_count, op_invocations))
        self.assertEqual(total_expected_count, len(invocations))

        # set state for next deployment assertion
        self.previous_instances = instances
        self.previous_ids = instance_ids

    def expectations(self):
        return {
            'compute': {
                'new': {},
                'existing': {},
                'removed': {}
            },
            'db': {
                'new': {},
                'existing': {},
                'removed': {}
            },
            'webserver': {
                'new': {},
                'existing': {},
                'removed': {}
            }
        }

    def deploy(self, resource_name, inputs=None):
        deployment, _ = deploy(resource('dsl/{0}.yaml'.format(resource_name)),
                               inputs=inputs)
        self.deployment_id = deployment.id
        return self.expectations()

    def scale(self, parameters):
        execute_workflow('scale', self.deployment_id, parameters=parameters)
        return self.expectations()

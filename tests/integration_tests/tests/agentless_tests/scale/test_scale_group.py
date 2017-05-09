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


from . import TestScaleBase


class TestScaleGroup(TestScaleBase):

    def test_group_scale(self):
        self.deploy_app('scale_groups')
        self._do_assertions(expected_node_count=1, assert_type='install')

        self.scale(parameters={'scalable_entity_name': 'group1', 'delta': 1})
        self._do_assertions(expected_node_count=2, assert_type='scale_out')

        self.scale(parameters={'scalable_entity_name': 'group1', 'delta': -1})
        self._do_assertions(expected_node_count=1, assert_type='scale_in')

    def _do_assertions(self, expected_node_count, assert_type):
        for node_id in ['compute', 'webserver', 'db']:
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

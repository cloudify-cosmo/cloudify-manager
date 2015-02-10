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

        expectations = self.scale(parameters={'node_id': 'compute'})
        expectations['compute']['new']['install'] = 1
        expectations['compute']['existing']['install'] = 1
        self.deployment_assertions(expectations)

    def test_compute_scale_in_compute(self):
        expectations = self.deploy('scale4')
        expectations['compute']['new']['install'] = 3
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={'node_id': 'compute',
                                              'delta': -1})
        expectations['compute']['existing']['install'] = 2
        expectations['compute']['removed']['install'] = 1
        expectations['compute']['removed']['uninstall'] = 1
        self.deployment_assertions(expectations)

    def test_compute_scale_out_2_compute(self):
        expectations = self.deploy('scale1')
        expectations['compute']['new']['install'] = 1
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={'node_id': 'compute',
                                              'delta': 2})
        expectations['compute']['new']['install'] = 2
        expectations['compute']['existing']['install'] = 1
        self.deployment_assertions(expectations)

    def test_compute_scale_in_2_compute(self):
        expectations = self.deploy('scale4')
        expectations['compute']['new']['install'] = 3
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={'node_id': 'compute',
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

        expectations = self.scale(parameters={'node_id': 'compute'})
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

        expectations = self.scale(parameters={'node_id': 'compute',
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

        expectations = self.scale(parameters={'node_id': 'db'})
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

        expectations = self.scale(parameters={'node_id': 'db',
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

    def test_db_contained_in_compute_scale_out_db_operate_on_db(self):
        expectations = self.deploy('scale2')
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'node_id': 'db', 'operate_on_compute': False})
        expectations['compute']['existing']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        self.deployment_assertions(expectations)

    def test_db_contained_in_compute_scale_in_db_operate_on_db(self):
        expectations = self.deploy('scale5')
        expectations['compute']['new']['install'] = 2
        expectations['db']['new']['install'] = 4
        expectations['db']['new']['rel_install'] = 8
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={'node_id': 'db',
                                              'delta': -1,
                                              'operate_on_compute': False})
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

        expectations = self.scale(parameters={'node_id': 'compute'})
        expectations['compute']['new']['install'] = 1
        expectations['compute']['existing']['install'] = 1
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        expectations['db']['existing']['scale_rel_install'] = 2
        self.deployment_assertions(expectations)

    def test_db_connected_to_compute_scale_out_db(self):
        expectations = self.deploy('scale3')
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={'node_id': 'db'})
        expectations['compute']['existing']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        self.deployment_assertions(expectations)

    def setUp(self):
        super(TestScaleWorkflow, self).setUp()
        self.previous_ids = []
        self.previous_instances = []

    def deployment_assertions(self, expected):
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

        instances = self.client.node_instances.list()
        instance_ids = [i.id for i in instances]

        calculated_expected = {}
        for node_id, expectations in expected.items():
            new_expectation = expectations['new']
            existing_expectation = expectations['existing']
            removed_expectation = expectations['removed']
            node_instances = [i for i in instances if i.node_id == node_id]
            new_instances = [i for i in node_instances
                             if i.id not in self.previous_ids]
            existing_instances = [i for i in node_instances
                                  if i.id in self.previous_ids]
            removed_instances = [i for i in self.previous_instances
                                 if i.id not in instance_ids
                                 and i.node_id == node_id]
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
            'testmockoperations', self.deployment_id)[
            'mock_operation_invocation']
        total_expected_count = 0
        for instance_id, operations in calculated_expected.items():
            for operation, expected_count in operations.items():
                total_expected_count += expected_count
                op_invocations = [i for i in invocations
                                  if i['operation'] == operation
                                  and i['id'] == instance_id]
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

    def deploy(self, resource_name):
        deployment, _ = deploy(resource('dsl/{0}.yaml'.format(resource_name)))
        self.deployment_id = deployment.id
        return self.expectations()

    def scale(self, parameters):
        execute_workflow('scale', self.deployment_id, parameters=parameters)
        return self.expectations()

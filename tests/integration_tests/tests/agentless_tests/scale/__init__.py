########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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


from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource


class TestScaleBase(AgentlessTestCase):

    def setUp(self):
        super(TestScaleBase, self).setUp()
        self.previous_ids = []
        self.previous_instances = []

    def deploy_app(self, resource_name, inputs=None, timeout_seconds=240):
        deployment, _ = self.deploy_application(
                resource('dsl/{0}.yaml'.format(resource_name)),
                timeout_seconds=timeout_seconds,
                inputs=inputs)
        self.deployment_id = deployment.id
        return self.expectations()

    def scale(self, parameters):
        self.execute_workflow('scale',
                              self.deployment_id,
                              parameters=parameters)
        return self.expectations()

    def expectations(self):
        return {
            'compute': {
                'new': {},
                'existing': {},
            },
            'db': {
                'new': {},
                'existing': {},
            },
            'webserver': {
                'new': {},
                'existing': {},
            }
        }

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
                'establish': (rel_install_count + scale_rel_install_count) / num_instances  # noqa
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
            node_instances = [i for i in instances if i.node_id == node_id]
            new_instances = [i for i in node_instances
                             if i.id not in self.previous_ids]
            existing_instances = [i for i in node_instances
                                  if i.id in self.previous_ids]
            import pydevd
            pydevd.settrace('192.168.43.135', port=53200, stdoutToServer=True,
                            stderrToServer=True)
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
            for new_instance in new_instances:
                calculated_expected.update({
                    new_instance.id: expected_invocations(
                            new_expectation, len(new_instances))})
            for existing_instance in existing_instances:
                calculated_expected.update({
                    existing_instance.id: expected_invocations(
                            existing_expectation, len(existing_instances))})

        invocations = self._get_operation_invocations(self.deployment_id)
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

    def _get_operation_invocations(self, deployment_id):
        invocation_lists = self.get_runtime_property(
            deployment_id, 'mock_operation_invocation')
        invocations = []
        for lst in invocation_lists:
            invocations.extend(lst)
        return invocations

    def _clear_operation_invocations(self, deployment_id):
        for inst in self.client.node_instances.list(
                deployment_id=deployment_id):
            if 'mock_operation_invocation' in inst.runtime_properties:
                inst.runtime_properties['mock_operation_invocation'] = {}

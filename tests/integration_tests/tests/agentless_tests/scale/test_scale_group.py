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

import pytest

from . import TestScaleBase

pytestmark = pytest.mark.group_scale


@pytest.mark.usefixtures('testmockoperations_plugin')
class TestScaleGroup(TestScaleBase):

    def test_group_scale(self):
        self.deploy_app('scale_groups', timeout_seconds=120)
        self._do_assertions(expected_node_count=1, assert_type='install')

        self.scale(parameters={'scalable_entity_name': 'group1', 'delta': 1})
        self._do_assertions(expected_node_count=2, assert_type='scale_out')

    def _do_assertions(self, expected_node_count, assert_type):
        for node_id in ['compute', 'webserver', 'db']:
            self.assertEqual(
                    expected_node_count,
                    len(self.client.node_instances.list(
                            deployment_id=self.deployment_id,
                            node_id=node_id).items)
            )
        invocations = self._get_operation_invocations(self.deployment_id)

        rel_ops = ['preconfigure', 'postconfigure', 'establish', 'unlink']
        lifecycle_install_ops = ['create', 'configure', 'start']
        lifecycle_install_ops_and_rel_ops = ['create',
                                             'preconfigure',
                                             'configure',
                                             'postconfigure',
                                             'start',
                                             'establish']
        if assert_type in ['install', 'scale_out']:
            expected = [
                ('compute', lifecycle_install_ops, None),
                ('webserver', lifecycle_install_ops_and_rel_ops,
                 'compute'),
                ('db', lifecycle_install_ops_and_rel_ops, 'webserver')]
        else:
            self.fail('Unsupported {0}'.format(assert_type))

        for expected_invocations in expected:
            node_id, operations, target_id = expected_invocations
            for operation in operations:

                rel_op = operation in rel_ops
                node_id_key = 'source' if rel_op else 'node'
                count = expected_node_count * (2 if rel_op else 1)

                matching_invocations = [i for i in invocations
                                        if operation == i['operation']
                                        and node_id == i[node_id_key]]
                assert len(matching_invocations) == count
                if rel_op:
                    for invocation in matching_invocations:
                        self.assertEqual(target_id, invocation['target'])

        self._clear_operation_invocations(self.deployment_id)

    def test_get_attribute_instance_context(self):
        # a blueprint that contains a single node template which contains a
        # get_attribute call in its properties, however that get_attribute
        # would need to resolve a runtime property! to resolve that,
        # resolving node properties would need to know what instance
        # to fetch runtime properties from, which is non-obvious when
        # there's more than one instance
        bp = """
tosca_definitions_version: cloudify_dsl_1_5
imports:
  - cloudify/types/types.yaml
node_types:
  t1:
    derived_from: cloudify.nodes.Root
    properties:
      prop1: {}
node_templates:
  node1:
    type: t1
    properties:
      prop1: {get_attribute: [node1, x]}
    interfaces:
      cloudify.interfaces.lifecycle:
        create: |
            from cloudify import ctx
            ctx.instance.runtime_properties['x'] = ctx.instance.id
        configure: |
          from cloudify import ctx
          ctx.instance.runtime_properties['result'] = \
            ctx.node.properties["prop1"]
"""
        self.upload_blueprint_resource(
            self.make_yaml_file(bp),
            blueprint_id='bp',
        )
        self.deploy_application(
            dsl_path=None,
            deployment_id='dep1',
            blueprint_id='bp',
        )

        # there's only one instance, and it had its id stored in the result
        # property, which was fetched from node properties in the configure
        # operation, where the node property was evaluated to resolve to the
        # other runtime property
        instances = self.client.node_instances.list(deployment_id='dep1')
        assert len(instances) == 1
        assert {ni.runtime_properties['result'] for ni in instances} == {
            instances[0].id
        }

        self.execute_workflow(
            'scale',
            'dep1',
            parameters={
                'scalable_entity_name': 'node1',
                'delta': 1,
            },
        )
        # now there's two node instances, and they still have the correct
        # runtime properties set!
        instances = self.client.node_instances.list(deployment_id='dep1')
        assert len(instances) == 2
        for ni in instances:
            assert ni.runtime_properties['result'] == ni.id

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
from contextlib import contextmanager

from . import TestScaleBase

pytestmark = pytest.mark.group_scale


@pytest.mark.usefixtures('testmockoperations_plugin')
class TestScaleOut(TestScaleBase):

    def test_compute_scale_out_compute(self):
        expectations = self.deploy_app('scale1')
        expectations['compute']['new']['install'] = 1
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute'})
        expectations['compute']['new']['install'] = 1
        expectations['compute']['existing']['install'] = 1
        self.deployment_assertions(expectations)

    def test_compute_scale_out_2_compute(self):
        expectations = self.deploy_app('scale1')
        expectations['compute']['new']['install'] = 1
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': 2})
        expectations['compute']['new']['install'] = 2
        expectations['compute']['existing']['install'] = 1
        self.deployment_assertions(expectations)

    def test_db_contained_in_compute_scale_out_compute(self):
        expectations = self.deploy_app('scale2')
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

    def test_db_contained_in_compute_scale_out_db(self):
        expectations = self.deploy_app('scale2')
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

    def test_db_contained_in_compute_scale_out_db_scale_db(self):
        expectations = self.deploy_app('scale2')
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

    def test_db_connected_to_compute_scale_out_compute(self):
        expectations = self.deploy_app('scale3')
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

    def test_db_connected_to_compute_scale_out_db(self):
        expectations = self.deploy_app('scale3')
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

    def test_db_contained_in_compute_scale_out_compute_rollback(self):
        fail_operations = [{
            'workflow': 'scale',
            'node': 'db',
            'operation': 'cloudify.interfaces.lifecycle.start'
        }]

        expectations = self.deploy_app(
                'scale8', inputs={'fail': fail_operations})
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        with self._set_retries(0):
            with self.assertRaises(RuntimeError) as e:
                self.scale(parameters={'scalable_entity_name': 'compute'})
        self.assertIn('Workflow execution failed:', str(e.exception))
        expectations = self.expectations()
        expectations['compute']['existing']['install'] = 1
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        self.deployment_assertions(expectations, rollback=True)

    def test_db_connected_to_compute_scale_out_compute_rollback(self):
        fail_operations = [{
            'workflow': 'scale',
            'node': 'compute',
            'operation': 'cloudify.interfaces.lifecycle.start'
        }]

        expectations = self.deploy_app(
                'scale9', inputs={'fail': fail_operations})
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        with self._set_retries(0):
            with self.assertRaises(RuntimeError) as e:
                self.scale(parameters={'scalable_entity_name': 'compute'})
        self.assertIn('Workflow execution failed:', str(e.exception))
        expectations = self.expectations()
        expectations['compute']['existing']['install'] = 1
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        self.deployment_assertions(expectations, rollback=True)

    def test_compute_scale_out_compute_rollback(self):
        fail_operations = [{
            'workflow': 'scale',
            'node': 'compute',
            'operation': 'cloudify.interfaces.lifecycle.start'
        }]

        expectations = self.deploy_app(
                'scale7', inputs={'fail': fail_operations})
        expectations['compute']['new']['install'] = 1
        self.deployment_assertions(expectations)

        with self._set_retries(0):
            with self.assertRaises(RuntimeError) as e:
                self.scale(parameters={'scalable_entity_name': 'compute'})
        self.assertIn('Workflow execution failed:', str(e.exception))
        expectations = self.expectations()
        expectations['compute']['existing']['install'] = 1
        self.deployment_assertions(expectations, rollback=True)

    def test_db_contained_in_compute_scale_out_compute_doesnt_rollback(self):
        """This test runs a scale out workflow on the db node. It fails
        at the "start" operation of that node and makes sure that no rollback
        has been made.
        """
        fail_operations = [{
            'workflow': 'scale',
            'node': 'db',
            'operation': 'cloudify.interfaces.lifecycle.start'
        }]

        expectations = self.deploy_app(
            'scale8', inputs={'fail': fail_operations})
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        with self._set_retries(0):
            with self.assertRaises(RuntimeError) as e:
                self.scale(parameters={'scalable_entity_name': 'compute',
                                       'rollback_if_failed': False})
        self.assertIn('Workflow execution failed:', str(e.exception))
        expectations = self.expectations()
        expectations['compute']['new']['install'] = 1
        expectations['compute']['new']['uninstall'] = 0
        expectations['compute']['existing']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        # this is somewhat of a hack. scale_rel_install only considers
        # establish, so we reuse this to decrease 2 from the expected establish
        # invocation, as start is the one that fails.
        # whoever you are that may be reading this. please don't hate me.
        # i mean no harm
        expectations['db']['new']['scale_rel_install'] = -2
        expectations['db']['new']['uninstall'] = 0
        expectations['db']['new']['rel_uninstall'] = 0
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        self.deployment_assertions(expectations)

    def test_db_connected_to_compute_scale_out_compute_doesnt_rollback(self):
        """This test runs a scale out workflow on the compute node. It fails
        at the "start" operation of that node and makes sure that no rollback
        has been made.
        """
        fail_operations = [{
            'workflow': 'scale',
            'node': 'compute',
            'operation': 'cloudify.interfaces.lifecycle.start'
        }]

        expectations = self.deploy_app(
            'scale9', inputs={'fail': fail_operations})
        expectations['compute']['new']['install'] = 1
        expectations['db']['new']['install'] = 1
        expectations['db']['new']['rel_install'] = 2
        self.deployment_assertions(expectations)

        with self._set_retries(0):
            with self.assertRaises(RuntimeError) as e:
                self.scale(parameters={'scalable_entity_name': 'compute',
                                       'rollback_if_failed': False})
        self.assertIn('Workflow execution failed:', str(e.exception))
        expectations = self.expectations()
        expectations['compute']['new']['install'] = 1
        expectations['compute']['new']['uninstall'] = 0
        expectations['compute']['existing']['install'] = 1
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['rel_install'] = 2
        expectations['db']['existing']['rel_uninstall'] = 0
        self.deployment_assertions(expectations)

    def test_compute_scale_out_compute_doesnt_rollback(self):
        """This test runs a scale out workflow on the compute node. It fails
        at the "start" operation of that node and makes sure that no rollback
        has been made.
        """
        fail_operations = [{
            'workflow': 'scale',
            'node': 'compute',
            'operation': 'cloudify.interfaces.lifecycle.start'
        }]

        expectations = self.deploy_app(
            'scale7', inputs={'fail': fail_operations})
        expectations['compute']['new']['install'] = 1
        self.deployment_assertions(expectations)
        with self._set_retries(0):
            with self.assertRaises(RuntimeError) as e:
                self.scale(parameters={'scalable_entity_name': 'compute',
                                       'rollback_if_failed': False})
        self.assertIn('Workflow execution failed:', str(e.exception))
        expectations = self.expectations()
        expectations['compute']['new']['install'] = 1
        expectations['compute']['new']['uninstall'] = 0
        expectations['compute']['existing']['install'] = 1
        self.deployment_assertions(expectations)

    @contextmanager
    def _set_retries(self, retries, retry_interval=0):
        original_config = {
            c.name: c.value for c in
            self.get_config(scope='workflow')
        }
        self.client.manager.put_config('task_retries', retries)
        self.client.manager.put_config('subgraph_retries', retries)
        self.client.manager.put_config('task_retry_interval', retry_interval)
        try:
            yield
        finally:
            for name, value in original_config.items():
                self.client.manager.put_config(name, value)

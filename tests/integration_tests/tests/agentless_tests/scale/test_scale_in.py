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
class TestScaleCompute(TestScaleBase):

    def test_compute_scale_in_compute(self):
        expectations = self.deploy_app('scale4')
        expectations['compute']['new']['install'] = 3
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': -1})
        expectations['compute']['existing']['install'] = 2
        self.deployment_assertions(expectations)

    def test_compute_scale_in_compute_ignore_failure_true(self):
        expectations = self.deploy_app('scale_ignore_failure')
        expectations['compute']['new']['install'] = 3
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'ignore_failure': True,
            'delta': -1})
        expectations['compute']['existing']['install'] = 2
        self.deployment_assertions(expectations)

    def test_compute_scale_in_compute_ignore_failure_false(self):
        expectations = self.deploy_app('scale_ignore_failure')
        expectations['compute']['new']['install'] = 3
        self.deployment_assertions(expectations)

        try:
            self.scale(parameters={
                'scalable_entity_name': 'compute',
                'ignore_failure': False,
                'delta': -1})
        except RuntimeError as e:
            self.assertIn("Workflow execution failed:", str(e))
        else:
            self.fail()

    def test_compute_scale_out_and_in_compute_from_0(self):
        expectations = self.deploy_app('scale10')
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
        self.deployment_assertions(expectations)

    def test_compute_scale_in_2_compute(self):
        expectations = self.deploy_app('scale4')
        expectations['compute']['new']['install'] = 3
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': -2})
        expectations['compute']['existing']['install'] = 1
        self.deployment_assertions(expectations)

    def test_db_contained_in_compute_scale_in_compute(self):
        expectations = self.deploy_app('scale5', timeout_seconds=120)
        expectations['compute']['new']['install'] = 2
        expectations['db']['new']['install'] = 4
        expectations['db']['new']['rel_install'] = 8
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': -1})
        expectations['compute']['existing']['install'] = 1
        expectations['db']['existing']['install'] = 2
        expectations['db']['existing']['rel_install'] = 4
        self.deployment_assertions(expectations)

    def test_db_connected_to_compute_scale_in_db(self):
        expectations = self.deploy_app('scale6')
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
        self.deployment_assertions(expectations)

    def test_db_connected_to_compute_scale_in_compute(self):
        expectations = self.deploy_app('scale6')
        expectations['compute']['new']['install'] = 2
        expectations['db']['new']['install'] = 2
        expectations['db']['new']['rel_install'] = 8
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'compute',
            'delta': -1})
        expectations['compute']['existing']['install'] = 1
        expectations['db']['existing']['install'] = 2
        expectations['db']['existing']['rel_install'] = 8
        expectations['db']['existing']['rel_uninstall'] = 4
        self.deployment_assertions(expectations)

    def test_db_connected_to_compute_scale_in_and_out_compute_from_0(self):
        expectations = self.deploy_app('scale11')
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
        expectations['db']['existing']['install'] = 1
        expectations['db']['existing']['scale_rel_install'] = 2
        expectations['db']['existing']['rel_uninstall'] = 2
        self.deployment_assertions(expectations)

    def test_db_contained_in_compute_scale_in_db_scale_db(self):
        expectations = self.deploy_app('scale5', timeout_seconds=120)
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
        self.deployment_assertions(expectations)

    def test_db_contained_in_compute_scale_in_db(self):
        expectations = self.deploy_app('scale5')
        expectations['compute']['new']['install'] = 2
        expectations['db']['new']['install'] = 4
        expectations['db']['new']['rel_install'] = 8
        self.deployment_assertions(expectations)

        expectations = self.scale(parameters={
            'scalable_entity_name': 'db',
            'delta': -1,
            'scale_compute': True})
        expectations['compute']['existing']['install'] = 1
        expectations['db']['existing']['install'] = 2
        expectations['db']['existing']['rel_install'] = 4
        self.deployment_assertions(expectations)

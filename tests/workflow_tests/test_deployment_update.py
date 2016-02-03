# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from dsl_parser.parser import parse_from_path
from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
# from manager_rest.blueprints_manager import get_blueprints_manager


class TestDeploymentUpdate(TestCase):

    # def setUp(self):
        # super(TestCase, self).setUp()
        # initial_blueprint = resource('dsl/dep_up_initial.yaml')
        # self.deployment, _ = deploy(initial_blueprint)

    def test_add_node(self):
        initial_blueprint_path = \
            resource('dsl/deployment_update/dep_up_initial.yaml')
        deployment, _ = deploy(initial_blueprint_path)

        new_blueprint_path = \
            resource('dsl/deployment_update/dep_up_add_node.yaml')
        blueprint = parse_from_path(new_blueprint_path)

        dep_mod = \
            self.client.deployment_updates.stage(deployment.id,
                                                 blueprint)
        step = \
            self.client.deployment_updates.add(dep_mod.id,
                                               entity_type='node',
                                               entity_id='site_1')
        print step
        self.client.deployment_updates.commit(dep_mod.id)

        added_nodes = self.client.nodes.list(deployment_id=deployment.id,
                                             node_id='site_1')
        self.assertEquals(1, len(added_nodes))

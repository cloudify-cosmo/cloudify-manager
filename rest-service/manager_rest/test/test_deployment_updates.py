#########
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

import re

from nose.plugins.attrib import attr

from manager_rest.test import base_test
from cloudify_rest_client.exceptions import CloudifyClientError
from dsl_parser.parser import parse_from_path
from utils import get_resource as resource


@attr(client_min_version=2, client_max_version=base_test.LATEST_API_VERSION)
class DeploymentUpdatesTestCase(base_test.BaseServerTestCase):

    def test_get_empty(self):
        result = self.client.deployment_updates.list()
        self.assertEquals(0, len(result))

    def test_stage(self):
        deployment_id = 'dep'

        dep_update = self._stage(deployment_id)

        self.assertEquals('staged', dep_update.state)
        self.assertEquals(deployment_id, dep_update.deployment_id)

        # assert that deployment update id has deployment id prefix
        dep_up_id_regex = re.compile('^{}-'.format(deployment_id))
        self.assertRegexpMatches(dep_update.id, re.compile(dep_up_id_regex))

        # assert steps list is initialized and empty
        self.assertListEqual([], dep_update.steps)

    def test_step_invalid_operation(self):
        deployment_id = 'dep'
        deployment_update_id = self._stage(deployment_id).id
        step = {'operation': 'illegal_operation',
                'entity_type': 'node',
                'entity_id': 'site_1'}
        self.assertRaisesRegexp(CloudifyClientError,
                                'illegal modification operation',
                                self.client.deployment_updates.step,
                                deployment_update_id,
                                **step)

    def test_step_non_existent_entity_id(self):
        deployment_id = 'dep'
        deployment_update_id = self._stage(deployment_id).id
        step = {'operation': 'add',
                'entity_type': 'node',
                'entity_id': 'non_existent_id'}
        self.assertRaisesRegexp(CloudifyClientError,
                                "entity id {} doesn't exist"
                                .format(step['entity_id']),
                                self.client.deployment_updates.step,
                                deployment_update_id,
                                **step)

    def test_step_non_existent_entity_type(self):
        deployment_id = 'dep'
        deployment_update_id = self._stage(deployment_id).id
        step = {'operation': 'add',
                'entity_type': 'non_existent_type',
                'entity_id': 'site_1'}
        self.assertRaisesRegexp(CloudifyClientError,
                                'illegal modification entity type',
                                self.client.deployment_updates.step,
                                deployment_update_id,
                                **step)

    def test_step_add(self):
        deployment_id = 'dep'
        deployment_update_id = self._stage(deployment_id).id
        step = {'operation': 'add',
                'entity_type': 'node',
                'entity_id': 'site_1'}
        self.client.deployment_updates.step(deployment_update_id,
                                            **step)
        dep_update = \
            self.client.deployment_updates.list(deployment_id=deployment_id)[0]
        self.assertDictContainsSubset(step, dep_update.steps[0])

    def test_step_remove(self):
        deployment_id = 'dep'
        deployment_update_id = self._stage(deployment_id).id
        step = {
            'operation': 'remove',
            'entity_type': 'node',
            'entity_id': 'site_1'}
        self.client.deployment_updates.step(deployment_update_id,
                                            **step)
        dep_update = \
            self.client.deployment_updates.list(deployment_id=deployment_id)[0]
        self.assertDictContainsSubset(step, dep_update.steps[0])

    def test_one_active_update_per_deployment(self):
        deployment_id = 'dep'
        self._stage(deployment_id)
        self.assertRaisesRegexp(CloudifyClientError,
                                'is not committed yet',
                                self._stage,
                                **{'deployment_id': deployment_id,
                                   'deploy_first': False})

    def _stage(self, deployment_id, blueprint_path=None, deploy_first=True):
        blueprint_path = \
            blueprint_path or \
            resource('deployment_update/dep_up_add_node.yaml')
        blueprint = parse_from_path(blueprint_path)

        if deploy_first:
            self.put_deployment(deployment_id)

        return self.client.deployment_updates.stage(deployment_id, blueprint)

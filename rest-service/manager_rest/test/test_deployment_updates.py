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
import tempfile

import re
import shutil

from nose.plugins.attrib import attr

from manager_rest.test import base_test
from cloudify_rest_client.exceptions import CloudifyClientError
from utils import get_resource as resource
from utils import tar_blueprint


@attr(client_min_version=2.1, client_max_version=base_test.LATEST_API_VERSION)
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
                'entity_id': 'site1'}
        self.assertRaisesRegexp(CloudifyClientError,
                                'illegal modification operation',
                                self.client.deployment_updates.step,
                                deployment_update_id,
                                **step)

    def test_step_non_existent_entity_id(self):
        deployment_id = 'dep'
        deployment_update_id = self._stage(deployment_id).id

        non_existing_entity_id_steps = [
            # nodes
            {'operation': 'add',
             'entity_type': 'node',
             'entity_id': 'nodes:non_existent_id'},
            {'operation': 'remove',
             'entity_type': 'node',
             'entity_id': 'nodes:non_existent_id'},

            # relationships
            {'operation': 'add',
             'entity_type': 'relationship',
             'entity_id': 'nodes:site1:relationships:[1]'},
            {'operation': 'remove',
             'entity_type': 'relationship',
             'entity_id': 'nodes:site1:relationships:[1]'},

            # relationship operations
            {'operation': 'add',
             'entity_type': 'operation',
             'entity_id': 'nodes:site1:relationships:[1]:source_operations:'
                          'cloudify.interfaces.relationship_lifecycle'
                          '.establish'},
            {'operation': 'remove',
             'entity_type': 'operation',
             'entity_id': 'nodes:site1:relationships:[1]:source_operations:'
                          'cloudify.interfaces.relationship_lifecycle'
                          '.establish'},
            {'operation': 'modify',
             'entity_type': 'operation',
             'entity_id': 'nodes:site1:relationships:[1]:source_operations:'
                          'cloudify.interfaces.relationship_lifecycle'
                          '.establish'},

            # node operations
            {'operation': 'add',
             'entity_type': 'operation',
             'entity_id': 'nodes:site1:operations:'
                          'cloudify.interfaces.lifecycle.create1'},
            {'operation': 'remove',
             'entity_type': 'operation',
             'entity_id': 'nodes:site1:operations:'
                          'cloudify.interfaces.lifecycle.create1'},
            {'operation': 'modify',
             'entity_type': 'operation',
             'entity_id': 'nodes:site1:operations:'
                          'cloudify.interfaces.lifecycle.create1'},

            # properties
            {'operation': 'add',
             'entity_type': 'property',
             'entity_id': 'nodes:site1:properties:ip'},
            {'operation': 'remove',
             'entity_type': 'operation',
             'entity_id': 'nodes:site1:properties:ip'},
            {'operation': 'modify',
             'entity_type': 'operation',
             'entity_id': 'nodes:site1:properties:ip'},

        ]

        for step in non_existing_entity_id_steps:
            try:
                self.client.deployment_updates.step(deployment_update_id,
                                                    **step)
            except CloudifyClientError as e:
                self.assertEqual(e.status_code, 400)
                self.assertEqual(e.error_code,
                                 'unknown_modification_stage_error')
                self.assertIn(
                        "Entity type {0} with entity id {1}:"
                        .format(step['entity_type'], step['entity_id']),
                        e.message)
                break
            self.fail("entity id {0} of entity type {1} shouldn't be valid"
                      .format(step['entity_id'], step['entity_type']))

    def test_workflow_and_skip_conflict(self):
        deployment_id = 'dep'
        deployment_update_id = self._stage(deployment_id).id

        msg = ('skip_install has been set to {skip_install}, skip uninstall '
               'has been set to {skip_uninstall}, and a custom workflow {'
               'workflow_id} has been set to replace "update". However, '
               'skip_install and skip_uninstall are mutually exclusive '
               'with a custom workflow')

        conflicting_params_list = [
            {
                'skip_install': True,
                'skip_uninstall': True,
                'workflow_id': 'custom_workflow'
            },
            {
                'skip_install': True,
                'skip_uninstall': False,
                'workflow_id': 'custom_workflow'
            },
            {
                'skip_install': False,
                'skip_uninstall': True,
                'workflow_id': 'custom_workflow'
            },
        ]

        for conflicting_params in conflicting_params_list:
            self.assertRaisesRegexp(CloudifyClientError,
                                    msg.format(**conflicting_params),
                                    self.client.deployment_updates.commit,
                                    update_id=deployment_update_id,
                                    **conflicting_params)

    def test_step_non_existent_entity_type(self):
        deployment_id = 'dep'
        deployment_update_id = self._stage(deployment_id).id
        step = {'operation': 'add',
                'entity_type': 'non_existent_type',
                'entity_id': 'site1'}
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
                'entity_id': 'nodes:site1'}
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
            'entity_id': 'nodes:http_web_server'}
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

        if deploy_first:
            self.put_deployment(deployment_id)

        tempdir = tempfile.mkdtemp()
        try:
            archive_path = tar_blueprint(blueprint_path, tempdir)
            archive_url = 'file://{0}'.format(archive_path)

            return \
                self.client.deployment_updates.\
                stage_archive(deployment_id,
                              archive_url,
                              'dep_up_add_node.yaml')
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)

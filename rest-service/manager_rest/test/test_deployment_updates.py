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
import os
import re
import datetime

from mock import patch
from nose.plugins.attrib import attr
from nose.tools import nottest

from dsl_parser import exceptions as parser_exceptions

from manager_rest import archiving, models, storage_manager, utils
from manager_rest.deployment_update.constants import STATES
from manager_rest.test import base_test
from cloudify_rest_client.exceptions import CloudifyClientError
from utils import get_resource as resource


@attr(client_min_version=2.1, client_max_version=base_test.LATEST_API_VERSION)
class DeploymentUpdatesTestCase(base_test.BaseServerTestCase):

    def test_get_empty(self):
        result = self.client.deployment_updates.list()
        self.assertEquals(0, len(result))

    def test_invalid_blueprint_raises_invalid_blueprint_exception(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')

        with patch('dsl_parser.tasks.parse_dsl') as parse_dsl_mock:
            parse_dsl_mock.side_effect = \
                parser_exceptions.DSLParsingException('')
            # # It doesn't matter that we are updating the deployment with the
            # same blueprint, since we mocked the blueprint parsing process.
            response = self._update(deployment_id, 'no_output.yaml')
            self.assertEquals(400, response.status_code)
            self.assertEquals('invalid_blueprint_error',
                              response.json['error_code'])

    def test_missing_required_input_raises_missing_required_input_error(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')

        with patch('dsl_parser.tasks.prepare_deployment_plan') \
                as prepare_deployment_mock:

            prepare_deployment_mock.side_effect = \
                parser_exceptions.MissingRequiredInputError()

            response = self._update(deployment_id, 'no_output.yaml')
            self.assertEquals(400, response.status_code)
            self.assertEquals('missing_required_deployment_input_error',
                              response.json['error_code'])

    def test_unknown_input_raises_unknown_input_error(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')

        with patch('dsl_parser.tasks.prepare_deployment_plan') \
                as prepare_deployment_mock:

            prepare_deployment_mock.side_effect = \
                parser_exceptions.UnknownInputError()

            response = self._update(deployment_id, 'no_output.yaml')
            self.assertEquals(400, response.status_code)
            self.assertEquals('unknown_deployment_input_error',
                              response.json['error_code'])

    @patch('manager_rest.deployment_update.handlers.'
           'DeploymentUpdateNodeHandler.finalize')
    @patch('manager_rest.deployment_update.handlers.'
           'DeploymentUpdateNodeInstanceHandler.finalize')
    def test_set_update_at_field(self, *_):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')
        deployment = self.client.deployments.get(deployment_id=deployment_id)
        timestamp_before_update = \
            datetime.datetime.strptime(deployment['updated_at'],
                                       "%Y-%m-%dT%H:%M:%S.%fZ")
        self._update(deployment_id, 'one_output.yaml')
        deployment_update = self.client.deployment_updates.list(
            deployment_id=deployment_id)[0]
        self.client.deployment_updates.finalize_commit(deployment_update.id)
        deployment = self.client.deployments.get(deployment_id=deployment_id)
        timestamp_after_update = \
            datetime.datetime.strptime(deployment['updated_at'],
                                       "%Y-%m-%dT%H:%M:%S.%fZ")
        self.assertGreater(timestamp_after_update, timestamp_before_update)

    def test_step_add(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')
        step = {'action': 'add',
                'entity_type': 'output',
                'entity_id': 'outputs:custom_output'}

        self._update(deployment_id, 'one_output.yaml')
        dep_update = \
            self.client.deployment_updates.list(deployment_id=deployment_id)[0]
        self.assertEqual(1, len(dep_update.steps))
        self.assertDictContainsSubset(step, dep_update.steps[0])

    def test_step_remove(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'one_output.yaml')
        step = {'action': 'remove',
                'entity_type': 'output',
                'entity_id': 'outputs:custom_output'}

        self._update(deployment_id, 'no_output.yaml')
        dep_update = \
            self.client.deployment_updates.list(deployment_id=deployment_id)[0]
        self.assertEqual(1, len(dep_update.steps))
        self.assertDictContainsSubset(step, dep_update.steps[0])

    def test_step_modify(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'one_output.yaml')
        step = {'action': 'modify',
                'entity_type': 'output',
                'entity_id': 'outputs:custom_output'}

        self._update(deployment_id, 'change_output.yaml')
        dep_update = \
            self.client.deployment_updates.list(deployment_id=deployment_id)[0]
        self.assertEqual(1, len(dep_update.steps))
        self.assertDictContainsSubset(step, dep_update.steps[0])

    def test_workflow_and_skip_conflict(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')

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
            response = self._update(blueprint_name='no_output.yaml',
                                    deployment_id=deployment_id,
                                    **conflicting_params)
            self.assertEquals(response.json['message'],
                              msg.format(**conflicting_params))

    def test_one_active_update_per_deployment(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')
        self._update(deployment_id, 'one_output.yaml')
        response = self._update(deployment_id,
                                blueprint_name='one_output.yaml')
        self.assertEquals(response.json['error_code'], 'conflict_error')
        self.assertIn('there are deployment updates still active',
                      response.json['message'])

    def test_one_active_update_per_deployment_force_flag(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')
        response = self._update(deployment_id, 'one_output.yaml')
        first_update_id = response.json['id']
        response = self._update(deployment_id,
                                blueprint_name='one_output.yaml',
                                force=True)
        # the second update should be running because the force flag was used
        self.assertEquals(STATES.EXECUTING_WORKFLOW, response.json['state'])
        # the first update should be with failed state
        # because the execution had terminated but the deployment update
        # object wasn't in an end state
        first_update = self.client.deployment_updates.get(first_update_id)
        self.assertEquals(STATES.FAILED, first_update.state)

    def test_one_active_update_per_dep_force_flag_real_active_executions(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')
        response = self._update(deployment_id, 'one_output.yaml')
        first_update_id = response.json['id']
        first_execution_id = response.json['execution_id']

        # updating the execution's status to started to make the first update
        # really be active
        storage_manager._get_instance().update_execution_status(
            first_execution_id, models.Execution.STARTED, error='')
        self.client.executions.get(execution_id=first_execution_id)

        response = self._update(deployment_id,
                                blueprint_name='one_output.yaml',
                                force=True)
        # force flag is expected not to work because the first update is
        # still really running
        self.assertEquals(response.json['error_code'], 'conflict_error')
        self.assertIn('there are deployment updates still active',
                      response.json['message'])
        self.assertIn('the "force" flag was used',
                      response.json['message'])
        # verifying the first update wasn't set with a failed state by the
        # force flag call
        first_update = self.client.deployment_updates.get(first_update_id)
        self.assertEquals(STATES.EXECUTING_WORKFLOW, first_update.state)

    def _deploy_base(self,
                     deployment_id,
                     blueprint_name,
                     inputs=None):
        blueprint_path = os.path.join('resources',
                                      'deployment_update',
                                      'depup_step')
        self.put_deployment(deployment_id,
                            inputs=inputs,
                            blueprint_file_name=blueprint_name,
                            blueprint_dir=blueprint_path)

    def _update(self,
                deployment_id,
                blueprint_name,
                **kwargs):
        blueprint_path = resource(os.path.join('deployment_update',
                                               'depup_step'))

        archive_path = self.archive_mock_blueprint(
            archive_func=archiving.make_tarbz2file,
            blueprint_dir=blueprint_path)
        kwargs['application_file_name'] = blueprint_name

        return self.post_file('/deployment-updates/{0}/update/initiate'
                              .format(deployment_id),
                              archive_path,
                              query_params=kwargs)

    def test_storage_serialization_and_response(self):
        now = utils.get_formatted_timestamp()
        sm = storage_manager._get_instance()
        deployment_update = models.DeploymentUpdate(
                deployment_id='deployment-id',
                deployment_plan={'name': 'my-bp'},
                state='staged',
                id='depup-id',
                steps=(),
                deployment_update_nodes=None,
                deployment_update_node_instances=None,
                deployment_update_deployment=None,
                modified_entity_ids=None,
                execution_id='execution-id',
                created_at=now)
        sm.put_deployment_update(deployment_update)

        depup_from_client = self.client.deployment_updates.get('depup-id')
        depup_response_attributes = {'id', 'state', 'deployment_id', 'steps',
                                     'execution_id', 'created_at'}
        for att in depup_response_attributes:
            self.assertEqual(getattr(depup_from_client, att),
                             getattr(deployment_update, att))


@nottest
class DeploymentUpdatesStepAndStageTestCase(base_test.BaseServerTestCase):
    def test_step_invalid_operation(self):
        deployment_id = 'dep'
        deployment_update_id = self._stage(deployment_id).id
        step = {'action': 'illegal_operation',
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
            {'action': 'add',
             'entity_type': 'node',
             'entity_id': 'nodes:non_existent_id'},
            {'action': 'remove',
             'entity_type': 'node',
             'entity_id': 'nodes:non_existent_id'},

            # relationships
            {'action': 'add',
             'entity_type': 'relationship',
             'entity_id': 'nodes:site1:relationships:[1]'},
            {'action': 'remove',
             'entity_type': 'relationship',
             'entity_id': 'nodes:site1:relationships:[1]'},

            # relationship operations
            {'action': 'add',
             'entity_type': 'action',
             'entity_id': 'nodes:site1:relationships:[1]:source_operations:'
                          'cloudify.interfaces.relationship_lifecycle'
                          '.establish'},
            {'action': 'remove',
             'entity_type': 'action',
             'entity_id': 'nodes:site1:relationships:[1]:source_operations:'
                          'cloudify.interfaces.relationship_lifecycle'
                          '.establish'},
            {'action': 'modify',
             'entity_type': 'action',
             'entity_id': 'nodes:site1:relationships:[1]:source_operations:'
                          'cloudify.interfaces.relationship_lifecycle'
                          '.establish'},

            # node operations
            {'action': 'add',
             'entity_type': 'action',
             'entity_id': 'nodes:site1:operations:'
                          'cloudify.interfaces.lifecycle.create1'},
            {'action': 'remove',
             'entity_type': 'action',
             'entity_id': 'nodes:site1:operations:'
                          'cloudify.interfaces.lifecycle.create1'},
            {'action': 'modify',
             'entity_type': 'action',
             'entity_id': 'nodes:site1:operations:'
                          'cloudify.interfaces.lifecycle.create1'},

            # properties
            {'action': 'add',
             'entity_type': 'property',
             'entity_id': 'nodes:site1:properties:ip'},
            {'action': 'remove',
             'entity_type': 'action',
             'entity_id': 'nodes:site1:properties:ip'},
            {'action': 'modify',
             'entity_type': 'action',
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

    def test_stage(self):
        deployment_id = 'dep'

        dep_update = self._stage(deployment_id)

        self.assertEquals('staged', dep_update.state)
        self.assertEquals(deployment_id, dep_update.deployment_id)

        # assert that deployment update id has deployment id prefix
        dep_up_id_regex = re.compile('^{0}-'.format(deployment_id))
        self.assertRegexpMatches(dep_update.id, re.compile(dep_up_id_regex))

        # assert steps list is initialized and empty
        self.assertListEqual([], dep_update.steps)

    def test_step_non_existent_entity_type(self):
        deployment_id = 'dep'
        deployment_update_id = self._stage(deployment_id).id
        step = {'action': 'add',
                'entity_type': 'non_existent_type',
                'entity_id': 'site1'}

        self.assertRaisesRegexp(CloudifyClientError,
                                'illegal modification entity type',
                                self.client.deployment_updates.step,
                                deployment_update_id,
                                **step)

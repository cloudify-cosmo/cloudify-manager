#########
# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
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
import uuid
import datetime
import unittest

from pytest import mark
from mock import patch, MagicMock, call

from dsl_parser.constants import INTER_DEPLOYMENT_FUNCTIONS
from dsl_parser import exceptions as parser_exceptions, constants

from cloudify.models_states import ExecutionState
from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test import base_test
from manager_rest.storage import models
from manager_rest.test.attribute import attr
from manager_rest.deployment_update import handlers
from manager_rest.deployment_update.constants import STATES
from manager_rest.test.utils import get_resource as resource


class DeploymentUpdatesBase(base_test.BaseServerTestCase):
    def _update(self,
                deployment_id,
                blueprint_name,
                blueprint_id=None,
                **kwargs):
        blueprint_path = resource(os.path.join('deployment_update',
                                               'depup_step'))
        blueprint_id = blueprint_id or 'b-{0}'.format(uuid.uuid4())
        self.put_blueprint(blueprint_path, blueprint_name, blueprint_id)
        kwargs['blueprint_id'] = blueprint_id
        return self.put(
            '/deployment-updates/{0}/update/initiate'.format(deployment_id),
            data=kwargs
        )


@attr(client_min_version=2.1, client_max_version=base_test.LATEST_API_VERSION)
class DeploymentUpdatesTestCase(DeploymentUpdatesBase):

    execution_parameters = {
        'added_instance_ids',
        'added_target_instances_ids',
        'removed_instance_ids',
        'remove_target_instance_ids',
        'extended_instance_ids',
        'extend_target_instance_ids',
        'reduced_instance_ids',
        'reduce_target_instance_ids'
    }

    def test_get_empty(self):
        result = self.client.deployment_updates.list()
        self.assertEqual(0, len(result))

    def test_invalid_blueprint_raises_invalid_blueprint_exception(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')

        with patch('dsl_parser.tasks.parse_dsl') as parse_dsl_mock:
            parse_dsl_mock.side_effect = \
                parser_exceptions.DSLParsingException('')
            # # It doesn't matter that we are updating the deployment with the
            # same blueprint, since we mocked the blueprint parsing process.
            self.assertRaisesRegex(RuntimeError,
                                   'invalid_blueprint_error',
                                   self._update,
                                   deployment_id,
                                   'no_output.yaml')

    def test_missing_required_input_raises_missing_required_input_error(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')

        with patch('dsl_parser.tasks.prepare_deployment_plan') \
                as prepare_deployment_mock:

            prepare_deployment_mock.side_effect = \
                parser_exceptions.MissingRequiredInputError()

            response = self._update(deployment_id, 'no_output.yaml')
            self.assertEqual(400, response.status_code)
            self.assertEqual('missing_required_deployment_input_error',
                             response.json['error_code'])

    def test_unknown_input_raises_unknown_input_error(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')

        with patch('dsl_parser.tasks.prepare_deployment_plan') \
                as prepare_deployment_mock:

            prepare_deployment_mock.side_effect = \
                parser_exceptions.UnknownInputError()

            response = self._update(deployment_id, 'no_output.yaml')
            self.assertEqual(400, response.status_code)
            self.assertEqual('unknown_deployment_input_error',
                             response.json['error_code'])

    def test_add_node_and_relationship(self):
        deployment_id = 'dep'
        changed_params = ['added_instance_ids', 'added_target_instances_ids']
        self._deploy_base(deployment_id,
                          'one_node.yaml')

        self._update(deployment_id, 'two_nodes.yaml', 'first')
        dep_update = \
            self.client.deployment_updates.list(deployment_id=deployment_id,
                                                _include=['execution_id'])[0]
        execution = self.client.executions.get(dep_update.execution_id)

        for param in self.execution_parameters:
            self.assertEqual(1 if param in changed_params else 0,
                             len(execution.parameters[param]))

        executions = self.client.executions.list()
        self.assertEqual('first', executions[1]['blueprint_id'])
        self.assertEqual('blueprint', executions[0]['blueprint_id'])

    def test_remove_node_and_relationship(self):
        deployment_id = 'dep'
        changed_params = ['removed_instance_ids', 'remove_target_instance_ids']

        self._deploy_base(deployment_id, 'two_nodes.yaml')

        self._update(deployment_id, 'one_node.yaml')
        dep_update = \
            self.client.deployment_updates.list(deployment_id=deployment_id)[0]

        execution = self.client.executions.get(dep_update.execution_id)
        for param in self.execution_parameters:
            self.assertEqual(1 if param in changed_params else 0,
                             len(execution.parameters[param]))

    def test_add_relationship(self):
        deployment_id = 'dep'
        changed_params = ['extended_instance_ids',
                          'extend_target_instance_ids']

        self._deploy_base(deployment_id, 'one_relationship.yaml')

        self._update(deployment_id, 'two_relationships.yaml')
        dep_update = \
            self.client.deployment_updates.list(deployment_id=deployment_id)[0]

        execution = self.client.executions.get(dep_update.execution_id)
        for param in self.execution_parameters:
            self.assertEqual(1 if param in changed_params else 0,
                             len(execution.parameters[param]))

    def test_remove_relationship(self):
        deployment_id = 'dep'
        changed_params = ['reduced_instance_ids', 'reduce_target_instance_ids']

        self._deploy_base(deployment_id, 'two_relationships.yaml')

        self._update(deployment_id, 'one_relationship.yaml')
        dep_update = \
            self.client.deployment_updates.list(deployment_id=deployment_id)[0]

        execution = self.client.executions.get(dep_update.execution_id)
        for param in self.execution_parameters:
            self.assertEqual(1 if param in changed_params else 0,
                             len(execution.parameters[param]),
                             '{0}:{1}'.format(param, execution.parameters[
                                 param]))

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

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    @patch('manager_rest.deployment_update.handlers.'
           'DeploymentUpdateNodeHandler.finalize')
    @patch('manager_rest.deployment_update.handlers.'
           'DeploymentUpdateNodeInstanceHandler.finalize')
    def test_update_execution_attributes(self, *_):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')
        deployment = self.client.deployments.get(deployment_id=deployment_id)
        self._update(deployment_id, 'one_output.yaml')
        dep_update = self.client.deployment_updates.list(
            deployment_id=deployment_id)[0]
        update_execution = self.client.executions.get(dep_update.execution_id)
        updated_deployment = \
            self.client.deployments.get(deployment_id=deployment_id)
        self.assertNotEqual(deployment.blueprint_id,
                            updated_deployment.blueprint_id)
        self.assertEqual(updated_deployment.blueprint_id,
                         update_execution.blueprint_id)
        self.assertIsNotNone(update_execution.started_at)

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

    def test_one_active_update_per_deployment(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')
        self._update(deployment_id, 'one_output.yaml')
        response = self._update(deployment_id,
                                blueprint_name='one_output.yaml')
        self.assertEqual(response.json['error_code'], 'conflict_error')
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
        self.assertEqual(STATES.EXECUTING_WORKFLOW, response.json['state'])
        # the first update should be with failed state
        # because the execution had terminated but the deployment update
        # object wasn't in an end state
        first_update = self.client.deployment_updates.get(first_update_id,
                                                          _include=['state'])
        self.assertEqual(STATES.FAILED, first_update.state)

    def test_one_active_update_per_dep_force_flag_real_active_executions(self):
        deployment_id = 'dep'
        self._deploy_base(deployment_id, 'no_output.yaml')
        response = self._update(deployment_id, 'one_output.yaml')
        first_update_id = response.json['id']
        first_execution_id = response.json['execution_id']

        # updating the execution's status to started to make the first update
        # really be active
        execution = self.sm.get(models.Execution, first_execution_id)
        execution.status = ExecutionState.STARTED
        self.sm.update(execution)
        self.client.executions.get(execution_id=first_execution_id)

        response = self._update(deployment_id,
                                blueprint_name='one_output.yaml',
                                force=True)
        # force flag is expected not to work because the first update is
        # still really running
        self.assertEqual(response.json['error_code'], 'conflict_error')
        self.assertIn('there are deployment updates still active',
                      response.json['message'])
        self.assertIn('the "force" flag was used',
                      response.json['message'])
        # verifying the first update wasn't set with a failed state by the
        # force flag call
        first_update = self.client.deployment_updates.get(first_update_id)
        self.assertEqual(STATES.EXECUTING_WORKFLOW, first_update.state)

    def _deploy_base(self,
                     deployment_id,
                     blueprint_name,
                     blueprint_id='blueprint',
                     inputs=None):
        blueprint_path = os.path.join('resources',
                                      'deployment_update',
                                      'depup_step')
        self.put_deployment(deployment_id,
                            inputs=inputs,
                            blueprint_file_name=blueprint_name,
                            blueprint_dir=blueprint_path,
                            blueprint_id=blueprint_id)

    def test_storage_serialization_and_response(self):
        blueprint = self._add_blueprint()
        deployment = self._add_deployment(blueprint)
        execution = self._add_execution(deployment)
        depup = self._add_deployment_update(deployment, execution)
        depup_from_client = self.client.deployment_updates.get(depup.id)
        depup_response_attributes = {'id', 'state', 'deployment_id', 'steps',
                                     'execution_id', 'created_at'}
        for att in depup_response_attributes:
            self.assertEqual(getattr(depup_from_client, att),
                             getattr(depup, att))


@mark.skip
class DeploymentUpdatesStepAndStageTestCase(base_test.BaseServerTestCase):
    def test_step_invalid_operation(self):
        deployment_id = 'dep'
        deployment_update_id = self._stage(deployment_id).id
        step = {'action': 'illegal_operation',
                'entity_type': 'node',
                'entity_id': 'site1'}
        self.assertRaisesRegex(CloudifyClientError,
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

        self.assertEqual('staged', dep_update.state)
        self.assertEqual(deployment_id, dep_update.deployment_id)

        # assert that deployment update id has deployment id prefix
        dep_up_id_regex = re.compile('^{0}-'.format(deployment_id))
        self.assertRegex(dep_update.id, re.compile(dep_up_id_regex))

        # assert steps list is initialized and empty
        self.assertListEqual([], dep_update.steps)

    def test_step_non_existent_entity_type(self):
        deployment_id = 'dep'
        deployment_update_id = self._stage(deployment_id).id
        step = {'action': 'add',
                'entity_type': 'non_existent_type',
                'entity_id': 'site1'}

        self.assertRaisesRegex(CloudifyClientError,
                               'illegal modification entity type',
                               self.client.deployment_updates.step,
                               deployment_update_id,
                               **step)


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class DeploymentUpdatesSourcePluginsTestCase(DeploymentUpdatesBase):

    def _deploy_base(self,
                     deployment_id,
                     blueprint_name,
                     inputs=None,
                     skip_plugins_validation=False):
        blueprint_path = os.path.join('resources',
                                      'deployment_update',
                                      'depup_step')
        self.put_deployment(deployment_id,
                            inputs=inputs,
                            blueprint_file_name=blueprint_name,
                            blueprint_dir=blueprint_path,
                            skip_plugins_validation=skip_plugins_validation)

    def test_plugin_installation_updates_plugins_by_default(self):
        def assert_all_not_in(plugin_names, plugins_set):
            for plugin_name in plugin_names:
                self.assertNotIn(plugin_name, plugins_set)

        def assert_all_in(plugin_names, plugins_set):
            for plugin_name in plugin_names:
                self.assertIn(plugin_name, plugins_set)

        deployment_id = 'dep'
        changed_params = ['update_plugins',
                          'central_plugins_to_install',
                          'central_plugins_to_uninstall']

        self._deploy_base(deployment_id, 'setup_with_plugin_1.yaml',
                          skip_plugins_validation=True)

        self._update(deployment_id, 'setup_with_plugin_2.yaml')
        dep_update = \
            self.client.deployment_updates.list(deployment_id=deployment_id)[0]

        execution = self.client.executions.get(dep_update.execution_id)
        for changed_param in changed_params:
            self.assertIn(changed_param, execution.parameters)

        self.assertTrue((execution.parameters['update_plugins']))
        central_plugins_to_install = {
            p[constants.PLUGIN_NAME_KEY]: p
            for p in execution.parameters[
                'central_plugins_to_install']}
        central_plugins_to_uninstall = {
            p[constants.PLUGIN_NAME_KEY]: p
            for p in execution.parameters['central_plugins_to_uninstall']}
        should_uninstall = {'should_reinstall',
                            'should_reinstall_v2',
                            'should_uninstall'}
        should_install = {'should_reinstall',
                          'should_reinstall_v2',
                          'should_install'}
        should_skip = ['should_skip_install', 'should_skip_install_v2']

        assert_all_in(should_uninstall, central_plugins_to_uninstall)
        assert_all_not_in(
            should_uninstall.difference(should_install),
            central_plugins_to_install)

        assert_all_in(should_install, central_plugins_to_install)
        assert_all_not_in(
            should_install.difference(should_uninstall),
            central_plugins_to_uninstall)

        assert_all_not_in(should_skip, central_plugins_to_uninstall)
        assert_all_not_in(should_skip, central_plugins_to_install)

        self.assertEqual(
            "1",
            central_plugins_to_uninstall['should_reinstall'][
                constants.PLUGIN_PACKAGE_VERSION])
        self.assertEqual(
            "2",
            central_plugins_to_uninstall['should_reinstall_v2'][
                constants.PLUGIN_PACKAGE_VERSION])
        self.assertEqual(
            "2",
            central_plugins_to_install['should_reinstall'][
                constants.PLUGIN_PACKAGE_VERSION])
        self.assertEqual(
            "1",
            central_plugins_to_install['should_reinstall_v2'][
                constants.PLUGIN_PACKAGE_VERSION])

    def test_plugin_updates_in_execution_is_disabled(self):
        deployment_id = 'dep'
        changed_params = ['update_plugins',
                          # Plugins to install and uninstall should be empty
                          # when update_plugins is False
                          'central_plugins_to_install',
                          'central_plugins_to_uninstall']

        self._deploy_base(deployment_id, 'setup_with_plugin_1.yaml',
                          skip_plugins_validation=True)

        self._update(
            deployment_id, 'setup_with_plugin_2.yaml', update_plugins=False)
        dep_update = \
            self.client.deployment_updates.list(deployment_id=deployment_id)[0]

        execution = self.client.executions.get(dep_update.execution_id)
        for changed_param in changed_params:
            self.assertIn(changed_param, execution.parameters)

        self.assertFalse(execution.parameters['update_plugins'])
        self.assertListEqual(
            execution.parameters['central_plugins_to_install'], [])
        self.assertListEqual(
            execution.parameters['central_plugins_to_uninstall'], [])


class TestDeploymentDependencies(unittest.TestCase):
    class MockDependency(dict):
        def __init__(self, dependency):
            self.update(dependency)

        @property
        def dependency_creator(self):
            return self['dependency_creator']

        @property
        def source_deployment(self):
            return self['source_deployment']

        @property
        def target_deployment(self):
            return self['target_deployment']

        @target_deployment.setter
        def target_deployment(self, value):
            self['target_deployment'] = value

    def setUp(self):
        self.mock_get_rm = patch('manager_rest.deployment_update.handlers'
                                 '.get_resource_manager')
        self.mock_get_rm.start()
        self.mock_sm = MagicMock()
        self.handler = handlers.DeploymentDependencies(self.mock_sm)
        self.mock_inter_deployment_dependency = patch(
            'manager_rest.storage.models.InterDeploymentDependencies')
        self.mock_inter_deployment_dependency.start(
        ).side_effect = lambda **_: self.MockDependency(_)
        self.mock_dep_update = MagicMock()
        self.mock_dep_update.deployment_plan = {INTER_DEPLOYMENT_FUNCTIONS: {}}
        self.mock_dep_update.deployment_id = 'test_deployment_id'

    def tearDown(self):
        self.mock_get_rm.stop()
        self.mock_inter_deployment_dependency.stop()
        super(TestDeploymentDependencies, self).tearDown()

    def _assert_sm_calls(self,
                         put_calls=None,
                         update_calls=None,
                         delete_calls=None):
        def assert_function_calls(sm_func, calls):
            if calls is None:
                sm_func.assert_not_called()
            else:
                sm_func.assert_has_calls(calls, any_order=True)

        assert_function_calls(self.mock_sm.put, put_calls)
        assert_function_calls(self.mock_sm.update, update_calls)
        assert_function_calls(self.mock_sm.delete, delete_calls)

    @staticmethod
    def _as_calls(_list):
        return [call(i) for i in _list]

    def _build_mock_dependency(self,
                               dependency_creator,
                               target_deployment=None):
        return self.MockDependency({
            'dependency_creator': dependency_creator,
            'target_deployment': target_deployment,
            'source_deployment': self.mock_dep_update.deployment_id
        })

    def test_does_nothing_with_empty_new_and_old_dependencies(self):
        curr_dependencies = []
        self.mock_sm.list.return_value = curr_dependencies
        self.handler._handle_dependency_changes(self.mock_dep_update,
                                                {},
                                                dep_plan_filter_func=_true)
        self._assert_sm_calls()

    def test_only_deletes_current_dependencies(self):
        curr_dependencies = [self._build_mock_dependency('creator_1')]
        self.mock_sm.list.return_value = curr_dependencies
        self.handler._handle_dependency_changes(self.mock_dep_update,
                                                {},
                                                dep_plan_filter_func=_true)
        self._assert_sm_calls(
            delete_calls=self._as_calls(curr_dependencies))

    def test_doesnt_delete_current_dependencies(self):
        curr_dependencies = [self._build_mock_dependency('creator_1')]
        self.mock_sm.list.return_value = curr_dependencies
        self.handler._handle_dependency_changes(
            self.mock_dep_update,
            {},
            dep_plan_filter_func=_true,
            keep_outdated_dependencies=True)
        self._assert_sm_calls()

    def test_only_adds_new_dependencies(self):
        curr_dependencies = []
        self.mock_sm.list.return_value = curr_dependencies
        dependency_creating_functions = {'creator_1': 'target_1'}
        self.mock_dep_update.deployment_plan[
            INTER_DEPLOYMENT_FUNCTIONS] = dependency_creating_functions
        self.handler._handle_dependency_changes(self.mock_dep_update,
                                                {},
                                                dep_plan_filter_func=_true)
        put_calls = self._as_calls(
            [self._build_mock_dependency('creator_1', 'target_1')]
        )
        self._assert_sm_calls(put_calls=put_calls)

    def test_creates_new_dependencies_and_deletes_current(self):
        curr_dependencies = [self._build_mock_dependency('creator_1')]
        self.mock_sm.list.return_value = curr_dependencies
        dependency_creating_functions = {'creator_2': 'target_1'}
        self.mock_dep_update.deployment_plan[
            INTER_DEPLOYMENT_FUNCTIONS] = dependency_creating_functions
        self.handler._handle_dependency_changes(self.mock_dep_update,
                                                {},
                                                dep_plan_filter_func=_true)
        put_calls = self._as_calls(
            [self._build_mock_dependency('creator_2', 'target_1')]
        )
        delete_calls = self._as_calls(curr_dependencies)
        self._assert_sm_calls(put_calls=put_calls,
                              delete_calls=delete_calls)

    def test_creates_new_deletes_current_updates_common_ignores_filtered(self):
        def ignores_ignore_me(dependency_creator):
            return dependency_creator != 'ignore_me'

        common_dependency_updated = self._build_mock_dependency(
            'creator_common_updated', 'target_old')
        common_dependency_isnt_updated = self._build_mock_dependency(
            'creator_common2', 'target_old')
        should_be_ignored = self._build_mock_dependency(
            'ignore_me', 'doesnt_matter')
        curr_dependencies = [
            self._build_mock_dependency('creator_1'),
            common_dependency_updated,
            common_dependency_isnt_updated,
            should_be_ignored
        ]
        self.mock_sm.list.return_value = curr_dependencies
        dependency_creating_functions = {
            'creator_2': 'target_1',
            common_dependency_updated.dependency_creator: 'target_new',
            common_dependency_isnt_updated.dependency_creator: 'target_old'
        }
        self.mock_dep_update.deployment_plan[
            INTER_DEPLOYMENT_FUNCTIONS] = dependency_creating_functions
        self.handler._handle_dependency_changes(
            self.mock_dep_update,
            {},
            dep_plan_filter_func=ignores_ignore_me)
        put_calls = self._as_calls(
            [
                self._build_mock_dependency('creator_2', 'target_1')
            ]
        )
        update_calls = self._as_calls(
            [
                self._build_mock_dependency(
                    common_dependency_updated.dependency_creator, 'target_new')
            ]
        )
        delete_calls = self._as_calls([curr_dependencies[0]])
        self._assert_sm_calls(put_calls=put_calls,
                              update_calls=update_calls,
                              delete_calls=delete_calls)
        missing_update_calls = self._as_calls([common_dependency_isnt_updated])
        try:
            self.mock_sm.update.assert_has_calls(missing_update_calls)
        except AssertionError:
            pass
        else:
            raise AssertionError("The calls {0} shouldn't have been used."
                                 "".format(missing_update_calls))

    def test_updates_all(self):
        common_dependency1 = self._build_mock_dependency(
            'creator_common_1', 'target_old_1')
        common_dependency2 = self._build_mock_dependency(
            'creator_common_2', 'target_old_2')
        curr_dependencies = [common_dependency1, common_dependency2]
        self.mock_sm.list.return_value = curr_dependencies
        dependency_creating_functions = {
            common_dependency1.dependency_creator: 'target_1_new',
            common_dependency2.dependency_creator: 'target_2_new'
        }
        self.mock_dep_update.deployment_plan[
            INTER_DEPLOYMENT_FUNCTIONS] = dependency_creating_functions
        self.handler._handle_dependency_changes(self.mock_dep_update,
                                                {},
                                                dep_plan_filter_func=_true)
        update_calls = self._as_calls(
            [
                self._build_mock_dependency(
                    common_dependency1.dependency_creator, 'target_1_new'),
                self._build_mock_dependency(
                    common_dependency2.dependency_creator, 'target_2_new')
            ]
        )
        self._assert_sm_calls(update_calls=update_calls)


def _true(*_, **__):
    return True

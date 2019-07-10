#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

from copy import deepcopy

import unittest
from mock import patch

from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify.models_states import ExecutionState

from dsl_parser.constants import (PLUGIN_NAME_KEY,
                                  WORKFLOW_PLUGINS_TO_INSTALL,
                                  DEPLOYMENT_PLUGINS_TO_INSTALL,
                                  HOST_AGENT_PLUGINS_TO_INSTALL)

from manager_rest.test import base_test
from manager_rest.test.attribute import attr
from manager_rest.test.base_test import BaseServerTestCase

from manager_rest.plugins_update.constants import STATES
from manager_rest.manager_exceptions import NotFoundError
from manager_rest.storage import get_storage_manager, models
from manager_rest.plugins_update.manager import \
        _did_plugins_to_install_change as plugins_to_install_change_detector


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class PluginsUpdatesBaseTest(BaseServerTestCase):
    def setUp(self):
        super(PluginsUpdatesBaseTest, self).setUp()

        def plugin_change_cleanup():
            if self.plugin_change_patched:
                self.plugin_change_patcher.stop()

        self.plugin_change_patcher = patch(
            'manager_rest.plugins_update.manager'
            '._did_plugins_to_install_change')
        self.plugin_change_patched = True
        self.plugin_change_patcher.start().return_value = True
        self.addCleanup(plugin_change_cleanup)


@attr(client_min_version=3.1,
      client_max_version=base_test.LATEST_API_VERSION)
class PluginsUpdatesTest(PluginsUpdatesBaseTest):

    def test_returns_relevant_plugins_updates(self):
        self.put_file(*self.put_blueprint_args(blueprint_id='hello_world'))
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update1 = self.client.plugins_update.update_plugins(
            'hello_world')
        plugins_update2 = self.client.plugins_update.update_plugins(
            'hello_world', force=True)
        plugins_update_set = set(p.id for p in self.client.plugins_update
                                 .list(_include=['id']).items)
        self.assertEqual(2, len(plugins_update_set))
        self.assertIn(plugins_update1.id, plugins_update_set)
        self.assertFalse(plugins_update1.forced)
        self.assertIn(plugins_update2.id, plugins_update_set)
        self.assertTrue(plugins_update2.forced)

    def test_returns_empty_list_with_no_plugins_updates(self):
        self.assertEqual(0, len(self.client.plugins_update.list().items))


@attr(client_min_version=3.1,
      client_max_version=base_test.LATEST_API_VERSION)
class PluginsUpdateIdTest(PluginsUpdatesBaseTest):

    def test_raises_when_plugins_update_doesnt_exist(self):
        with self.assertRaisesRegexp(
                CloudifyClientError,
                'Requested `PluginsUpdate` with ID `non_existing` was '
                'not found') as e:
            self.client.plugins_update.get('non_existing')
            self.assertEqual(404, e.exception.status_code)

    def test_returns_correct_plugins_update(self):
        self.put_file(*self.put_blueprint_args(blueprint_id='hello_world'))
        self.client.deployments.create('hello_world', 'd1')
        self.wait_for_deployment_creation(self.client, 'd1')
        plugins_update = self.client.plugins_update.update_plugins(
            'hello_world')
        response_plugins_update = self.client.plugins_update.get(
            plugins_update.id, _include=['id'])
        self.assertEqual(plugins_update.id, response_plugins_update.id)


@attr(client_min_version=3.1,
      client_max_version=base_test.LATEST_API_VERSION)
class PluginsUpdateTest(PluginsUpdatesBaseTest):
    """
    Test plugins update.
    """

    def setUp(self):
        super(PluginsUpdateTest, self).setUp()
        self._sm = get_storage_manager()

    def test_raises_with_nonexisting_blueprint(self):
        with self.assertRaises(CloudifyClientError) as e:
            self.client.plugins_update.update_plugins("non_existing")
            self.assertEqual(404, e.exception.status_code)

    def test_raises_blueprint_has_no_deployments(self):
        self.put_file(*self.put_blueprint_args(blueprint_id='hello_world'))
        with self.assertRaisesRegexp(CloudifyClientError,
                                     "The blueprint 'hello_world' has no "
                                     "deployments to update."):
            self.client.plugins_update.update_plugins("hello_world")

    def test_plugins_update_and_execution_parameters_are_correct(self):
        self.put_file(*self.put_blueprint_args(blueprint_id='hello_world'))
        self.client.deployments.create('hello_world', 'd1')
        self.wait_for_deployment_creation(self.client, 'd1')
        self.client.deployments.create('hello_world', 'd2')
        self.wait_for_deployment_creation(self.client, 'd2')
        plugins_update = self.client.plugins_update.update_plugins(
            'hello_world')
        self.assertListEqual(['d1', 'd2'],
                             plugins_update.deployments_to_update)
        execution = self.client.executions.get(plugins_update.execution_id)
        self.assertDictEqual(
            execution.parameters,
            {'update_id': plugins_update.id,
             'deployments_to_update': ['d1', 'd2'],
             'temp_blueprint_id': plugins_update.temp_blueprint_id})

    def test_raises_while_plugins_updates_are_active(self):
        self.put_file(*self.put_blueprint_args(blueprint_id='hello_world'))
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update = self.client.plugins_update.update_plugins(
            'hello_world')
        with self.assertRaisesRegexp(
                CloudifyClientError,
                'There are plugins updates still active, update IDs: '
                '{0}'.format(plugins_update.id)):
            self.client.plugins_update.update_plugins('hello_world')

    def test_doesnt_raise_while_plugins_updates_are_active_and_forced(self):
        self.put_file(*self.put_blueprint_args(blueprint_id='hello_world'))
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        self.client.plugins_update.update_plugins('hello_world')
        self.client.plugins_update.update_plugins('hello_world', True)

    def test_raises_with_real_active_plugins_updates_and_forced(self):
        self.put_file(*self.put_blueprint_args(blueprint_id='hello_world'))
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update = self.client.plugins_update.update_plugins(
            'hello_world')
        execution = self._sm.get(models.Execution, plugins_update.execution_id)
        execution.status = ExecutionState.STARTED
        self._sm.update(execution)
        with self.assertRaisesRegexp(
                CloudifyClientError,
                'There are plugins updates still active; the "force" flag '
                'was used yet these updates have actual executions running '
                'update IDs: {0}'.format(plugins_update.id)):
            self.client.plugins_update.update_plugins('hello_world', True)

    def test_raises_when_no_plugin_change_detected(self):
        self.plugin_change_patcher.stop()
        self.plugin_change_patched = False
        self.put_file(*self.put_blueprint_args(
            blueprint_id='host_agent_blueprint'))
        with self.assertRaisesRegexp(
                CloudifyClientError,
                'Found no plugins to update for "host_agent_blueprint" '
                'blueprint, aborting plugins update'):
            self.client.plugins_update.update_plugins('host_agent_blueprint')

    def test_finalize_raises_plugins_update_with_not_compatible_state(self):
        self.put_file(*self.put_blueprint_args(blueprint_id='hello_world'))
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update_id = self.client.plugins_update.update_plugins(
            'hello_world').id
        plugins_update = self._sm.get(models.PluginsUpdate, plugins_update_id)
        plugins_update.state = STATES.SUCCESSFUL
        self._sm.update(plugins_update)
        with self.assertRaisesRegexp(
                CloudifyClientError,
                "Cannot finalize plugins update .+, it's not in the "
                "{0} state\\.".format(STATES.EXECUTING_WORKFLOW)):
            self.client.plugins_update.finalize_plugins_update(
                plugins_update_id)

    def test_finalize_updates_original_blueprint_plan(self):
        self.put_file(*self.put_blueprint_args(blueprint_id='hello_world'))
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update_id = self.client.plugins_update.update_plugins(
            'hello_world').id
        blueprint = self._sm.get(models.Blueprint, 'hello_world')
        plan = deepcopy(blueprint.plan)
        plan[DEPLOYMENT_PLUGINS_TO_INSTALL].append('dummy')
        blueprint.plan = plan
        self._sm.update(blueprint)
        # Sanity check
        self.assertIn(
            'dummy',
            self._sm.get(models.Blueprint, 'hello_world')
                .plan[DEPLOYMENT_PLUGINS_TO_INSTALL])
        self.client.plugins_update.finalize_plugins_update(
            plugins_update_id)
        self.assertNotIn(
            'dummy',
            self._sm.get(models.Blueprint, 'hello_world')
                .plan[DEPLOYMENT_PLUGINS_TO_INSTALL])

    def test_finalize_updates_plugins_update_state(self):
        self.put_file(*self.put_blueprint_args(blueprint_id='hello_world'))
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update = self.client.plugins_update.update_plugins(
            'hello_world')
        self.assertNotEqual(plugins_update.state, STATES.SUCCESSFUL)
        plugins_update = self.client.plugins_update.finalize_plugins_update(
            plugins_update.id)
        self.assertEqual(plugins_update.state, STATES.SUCCESSFUL)

    def test_finalize_deletes_temp_blueprint(self):
        self.put_file(*self.put_blueprint_args(blueprint_id='hello_world'))
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update = self.client.plugins_update.update_plugins(
            'hello_world')
        self._sm.get(models.Blueprint, plugins_update.temp_blueprint_id)
        plugins_update = self.client.plugins_update.finalize_plugins_update(
            plugins_update.id)
        with self.assertRaises(NotFoundError):
            self._sm.get(models.Blueprint, plugins_update.temp_blueprint_id)


@attr(client_min_version=3.1,
      client_max_version=base_test.LATEST_API_VERSION)
class PluginsToInstallUpdateTest(unittest.TestCase):

    def test_detects_no_addition_identical_plan(self):
        temp_plan = {
            HOST_AGENT_PLUGINS_TO_INSTALL: [],
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        plan = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        self.assertFalse(plugins_to_install_change_detector(temp_plan, plan))

    def test_detects_no_addition_reduced_deployment_plugins(self):
        temp_plan = {
            HOST_AGENT_PLUGINS_TO_INSTALL: [],
            DEPLOYMENT_PLUGINS_TO_INSTALL: [],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        plan = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        self.assertFalse(plugins_to_install_change_detector(temp_plan, plan))

    def test_detects_no_addition_reduced_workflow_plugins(self):
        temp_plan = {
            HOST_AGENT_PLUGINS_TO_INSTALL: [],
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            WORKFLOW_PLUGINS_TO_INSTALL: []
        }
        plan = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        self.assertFalse(plugins_to_install_change_detector(temp_plan, plan))

    def test_detects_no_addition_reduced_host_agent_plugins(self):
        temp_plan = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            HOST_AGENT_PLUGINS_TO_INSTALL: [],
            WORKFLOW_PLUGINS_TO_INSTALL: []
        }
        plan = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            HOST_AGENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}],
            WORKFLOW_PLUGINS_TO_INSTALL: []
        }
        self.assertFalse(plugins_to_install_change_detector(temp_plan, plan))

    def test_detects_addition_in_deployment_plugins(self):
        temp_plan = {
            HOST_AGENT_PLUGINS_TO_INSTALL: [],
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: '', '': ''}],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        plan = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        self.assertTrue(plugins_to_install_change_detector(temp_plan, plan))

        temp_plan = {
            HOST_AGENT_PLUGINS_TO_INSTALL: [],
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        plan = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: [],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        self.assertTrue(plugins_to_install_change_detector(temp_plan, plan))

    def test_detects_addition_in_workflow_plugins(self):
        temp_plan = {
            HOST_AGENT_PLUGINS_TO_INSTALL: [],
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd', '': ''}]
        }
        plan = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        self.assertTrue(plugins_to_install_change_detector(temp_plan, plan))

        temp_plan = {
            HOST_AGENT_PLUGINS_TO_INSTALL: [],
            DEPLOYMENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        plan = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: [],
            WORKFLOW_PLUGINS_TO_INSTALL: []
        }
        self.assertTrue(plugins_to_install_change_detector(temp_plan, plan))

    def test_detects_addition_in_host_agent_plugins(self):
        temp_plan = {
            HOST_AGENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: '', '': ''}],
            DEPLOYMENT_PLUGINS_TO_INSTALL: [],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        plan = {
            HOST_AGENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            DEPLOYMENT_PLUGINS_TO_INSTALL: [],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        self.assertTrue(plugins_to_install_change_detector(temp_plan, plan))

        temp_plan = {
            HOST_AGENT_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: ''}],
            DEPLOYMENT_PLUGINS_TO_INSTALL: [],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        plan = {
            HOST_AGENT_PLUGINS_TO_INSTALL: [],
            DEPLOYMENT_PLUGINS_TO_INSTALL: [],
            WORKFLOW_PLUGINS_TO_INSTALL: [{PLUGIN_NAME_KEY: 'asd'}]
        }
        self.assertTrue(plugins_to_install_change_detector(temp_plan, plan))

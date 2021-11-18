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

from dsl_parser.constants import (PLUGIN_NAME_KEY,
                                  WORKFLOW_PLUGINS_TO_INSTALL,
                                  DEPLOYMENT_PLUGINS_TO_INSTALL,
                                  HOST_AGENT_PLUGINS_TO_INSTALL)

from manager_rest.test.base_test import BaseServerTestCase

from manager_rest.plugins_update.constants import STATES
from manager_rest.manager_exceptions import NotFoundError
from manager_rest.storage import get_storage_manager, models
from manager_rest.plugins_update.manager import \
    _did_plugins_to_install_change as plugins_to_install_change_detector
from manager_rest.plugins_update.constants import STATES as PluginsUpdateStates


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


class PluginsUpdatesTest(PluginsUpdatesBaseTest):

    def test_returns_relevant_plugins_updates(self):
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update1 = self.client.plugins_update.update_plugins(
            'hello_world')

        sm = get_storage_manager()
        update_entry = sm.get(models.PluginsUpdate, plugins_update1.id)
        update_entry.state = PluginsUpdateStates.FAILED
        sm.update(update_entry)

        plugins_update2 = self.client.plugins_update.update_plugins(
            'hello_world')
        plugins_update_set = set(p.id for p in self.client.plugins_update
                                 .list(_include=['id']).items)
        self.assertEqual(2, len(plugins_update_set))
        self.assertIn(plugins_update1.id, plugins_update_set)
        self.assertIn(plugins_update2.id, plugins_update_set)

    def test_returns_empty_list_with_no_plugins_updates(self):
        self.assertEqual(0, len(self.client.plugins_update.list().items))


class PluginsUpdateIdTest(PluginsUpdatesBaseTest):

    def test_raises_when_plugins_update_doesnt_exist(self):
        with self.assertRaisesRegex(
                CloudifyClientError,
                'Requested `PluginsUpdate` with ID `non_existing` was '
                'not found') as e:
            self.client.plugins_update.get('non_existing')
            self.assertEqual(404, e.exception.status_code)

    def test_returns_correct_plugins_update(self):
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd1')
        self.wait_for_deployment_creation(self.client, 'd1')
        plugins_update = self.client.plugins_update.update_plugins(
            'hello_world')
        response_plugins_update = self.client.plugins_update.get(
            plugins_update.id, _include=['id'])
        self.assertEqual(plugins_update.id, response_plugins_update.id)


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

    def test_plugins_update_runs_when_no_deployments_to_update(self):
        self.put_blueprint(blueprint_id='hello_world')
        plugins_update = self.client.plugins_update.update_plugins(
            'hello_world')
        self.assertEqual(plugins_update.state, STATES.EXECUTING_WORKFLOW)

    def test_plugins_update_and_execution_parameters_are_correct(self):
        self.put_blueprint(blueprint_id='hello_world')
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
             'temp_blueprint_id': plugins_update.temp_blueprint_id,
             'force': False,
             'auto_correct_types': False,
             'reevaluate_active_statuses': False})

    def test_plugins_update_auto_correct_types_flag(self):
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'dep')
        self.wait_for_deployment_creation(self.client, 'dep')
        plugins_update = self.client.plugins_update.update_plugins(
            'hello_world', auto_correct_types=True)
        self.assertEqual(['dep'], plugins_update.deployments_to_update)
        execution = self.client.executions.get(plugins_update.execution_id)
        self.assertIn('auto_correct_types', execution.parameters)
        self.assertEqual(True, execution.parameters.get('auto_correct_types'))

    def test_raises_while_plugins_updates_are_active(self):
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update = self.client.plugins_update.update_plugins(
            'hello_world')
        with self.assertRaisesRegex(
                CloudifyClientError,
                'There are plugins updates still active, update IDs: '
                '{0}'.format(plugins_update.id)):
            self.client.plugins_update.update_plugins('hello_world')

    def test_doesnt_raise_when_last_plugins_update_successful(self):
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update_id = self.client.plugins_update.update_plugins(
            'hello_world').id
        plugins_update = self._sm.get(models.PluginsUpdate, plugins_update_id)
        plugins_update.state = STATES.SUCCESSFUL
        self._sm.update(plugins_update)

        self.client.plugins_update.update_plugins('hello_world')

    def test_doesnt_raise_when_last_plugins_update_failed(self):
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update_id = self.client.plugins_update.update_plugins(
            'hello_world').id
        plugins_update = self._sm.get(models.PluginsUpdate, plugins_update_id)
        plugins_update.state = STATES.FAILED
        self._sm.update(plugins_update)

        self.client.plugins_update.update_plugins('hello_world')

    def test_doesnt_raise_when_last_plugins_update_didnt_do_anything(self):
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update_id = self.client.plugins_update.update_plugins(
            'hello_world').id
        plugins_update = self._sm.get(models.PluginsUpdate, plugins_update_id)
        plugins_update.state = STATES.NO_CHANGES_REQUIRED
        self._sm.update(plugins_update)

        self.client.plugins_update.update_plugins('hello_world')

    def test_no_changes_required_when_no_plugin_change_detected(self):
        self.plugin_change_patcher.stop()
        self.plugin_change_patched = False
        self.put_blueprint(blueprint_id='host_agent_blueprint')
        plugins_update = self.client.plugins_update.update_plugins(
            'host_agent_blueprint')
        self.assertEqual(plugins_update.state, STATES.NO_CHANGES_REQUIRED)

    def test_finalize_raises_plugins_update_with_not_compatible_state(self):
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update_id = self.client.plugins_update.update_plugins(
            'hello_world').id
        plugins_update = self._sm.get(models.PluginsUpdate, plugins_update_id)
        plugins_update.state = STATES.SUCCESSFUL
        self._sm.update(plugins_update)
        with self.assertRaisesRegex(
                CloudifyClientError,
                "Cannot finalize plugins update .+, it's not in the "
                "{0} state\\.".format(STATES.EXECUTING_WORKFLOW)):
            self.client.plugins_update.finalize_plugins_update(
                plugins_update_id)

    def test_finalize_updates_original_blueprint_plan(self):
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update_id = self.client.plugins_update.update_plugins(
            'hello_world').id
        blueprint = self._sm.get(models.Blueprint, 'hello_world')
        plan = deepcopy(blueprint.plan)
        plan[DEPLOYMENT_PLUGINS_TO_INSTALL].append('dummy')
        blueprint.plan = plan
        self._sm.update(blueprint)
        self.pretend_deployments_updated(plugins_update_id)
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
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update = self.client.plugins_update.update_plugins(
            'hello_world')
        self.assertNotEqual(plugins_update.state, STATES.SUCCESSFUL)
        self.pretend_deployments_updated(plugins_update.id)
        plugins_update = self.client.plugins_update.finalize_plugins_update(
            plugins_update.id)
        self.assertEqual(plugins_update.state, STATES.SUCCESSFUL)

    def test_finalize_deletes_temp_blueprint(self):
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update = self.client.plugins_update.update_plugins(
            'hello_world')
        self._sm.get(models.Blueprint, plugins_update.temp_blueprint_id)
        with self.assertRaises(CloudifyClientError):
            plugins_update = self.client.plugins_update.\
                finalize_plugins_update(plugins_update.id)
        with self.assertRaises(NotFoundError):
            self._sm.get(models.Blueprint, plugins_update.temp_blueprint_id)

    def test_finalize_error_if_deployments_not_updated(self):
        self.put_blueprint(blueprint_id='bp')
        self.client.deployments.create('bp', 'dep')
        self.wait_for_deployment_creation(self.client, 'dep')
        plugins_update = self.client.plugins_update.update_plugins('bp')
        self._sm.get(models.Blueprint, plugins_update.temp_blueprint_id)
        with self.assertRaises(CloudifyClientError) as ex:
            plugins_update = self.client.plugins_update.\
                finalize_plugins_update(plugins_update.id)
            self.assertEqual(STATES.FAILED, plugins_update.state)
            self.assertEqual(ex.status_code, 400)
            self.assertIn(str(ex), plugins_update.id)

    def test_finalize_no_deployments_updated(self):
        self.put_blueprint(blueprint_id='bp')
        self.client.deployments.create('bp', 'dep')
        self.wait_for_deployment_creation(self.client, 'dep')
        plugins_update = self.client.plugins_update.update_plugins('bp')
        self._sm.get(models.Blueprint, plugins_update.temp_blueprint_id)
        with self.assertRaises(CloudifyClientError):
            plugins_update = self.client.plugins_update.\
                finalize_plugins_update(plugins_update.id)
        self.assertRegex(plugins_update['temp_blueprint_id'],
                         r'^plugins-update\-.*\-bp$')
        self.assertEmpty(self._sm.list(
            models.Deployment,
            filters={'blueprint_id': plugins_update['temp_blueprint_id']},
        ).items)
        updated_deployment = self._sm.get(
            models.Deployment, plugins_update.deployments_to_update[0])
        self.assertEqual('bp', updated_deployment.blueprint.id)

    def test_deployments_partially_updated(self):
        """Test the case where only a part of deployments was updated."""
        self.put_blueprint(blueprint_id='bp')
        self.client.deployments.create('bp', 'dep1')
        self.wait_for_deployment_creation(self.client, 'dep1')
        self.client.deployments.create('bp', 'dep2')
        self.wait_for_deployment_creation(self.client, 'dep2')
        plugins_update = self.client.plugins_update.update_plugins('bp')
        self.pretend_deployments_updated(plugins_update.id, ['dep1'])
        with self.assertRaises(CloudifyClientError):
            plugins_update = self.client.plugins_update.\
                finalize_plugins_update(plugins_update.id)
        # Check "updated" deployment
        dep1 = self._sm.get(models.Deployment, 'dep1')
        self.assertEqual(plugins_update.temp_blueprint_id, dep1.blueprint.id)
        # Check not update deployment
        dep2 = self._sm.get(models.Deployment, 'dep2')
        self.assertEqual(plugins_update.blueprint_id, dep2.blueprint.id)

    def pretend_deployments_updated(self, plugins_update_id: str,
                                    deployment_ids: list = None):
        """Pretend those deployments were updated."""
        plugins_update = self._sm.get(models.PluginsUpdate,
                                      plugins_update_id)
        temp_blueprint = self._sm.get(models.Blueprint,
                                      plugins_update.temp_blueprint.id)
        if deployment_ids is None:
            deployment_ids = plugins_update.deployments_to_update
        for deployment_id in deployment_ids:
            deployment = self._sm.get(models.Deployment, deployment_id)
            deployment.blueprint = temp_blueprint
            self._sm.update(deployment)


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

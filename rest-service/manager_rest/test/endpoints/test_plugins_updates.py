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
from manager_rest.storage import models
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

        update_entry = self.sm.get(models.PluginsUpdate, plugins_update1.id)
        update_entry.state = PluginsUpdateStates.FAILED
        self.sm.update(update_entry)

        plugins_update2 = self.client.plugins_update.update_plugins(
            'hello_world')
        plugins_update_set = set(p.id for p in self.client.plugins_update
                                 .list(_include=['id']).items)
        self.assertEqual(2, len(plugins_update_set))
        self.assertIn(plugins_update1.id, plugins_update_set)
        self.assertIn(plugins_update2.id, plugins_update_set)

    def test_returns_empty_list_with_no_plugins_updates(self):
        self.assertEqual(0, len(self.client.plugins_update.list().items))

    def test_no_break_on_include_blueprint_columns(self):
        """Including two columns from the same table has made the storage
        manager unhappy in the past. Let's not do that again."""

        # Make sure we have a plugins update in case we skip listing when the
        # table is empty at any point in the future
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        result = self.client.plugins_update.update_plugins('hello_world')

        include_list = ['blueprint_id', 'temp_blueprint_id']
        expected_updates = [
            {
                k: v for k, v in result.items()
                if k in include_list
            }
        ]

        updates_list = self.client.plugins_update.list(_include=include_list)

        assert updates_list.items == expected_updates


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
        assert set(plugins_update.deployments_per_tenant[
                       plugins_update.tenant_name]
                   ) == {'d1', 'd2'}
        execution = self.client.executions.get(plugins_update.execution_id)
        self.assertDictEqual(
            execution.parameters,
            {'update_id': plugins_update.id,
             'deployments_to_update': None,
             'deployments_per_tenant': {'default_tenant': ['d1', 'd2']},
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
        assert plugins_update.deployments_per_tenant[
                       plugins_update.tenant_name] == ['dep']
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
        plugins_update = self.sm.get(models.PluginsUpdate, plugins_update_id)
        plugins_update.state = STATES.SUCCESSFUL
        self.sm.update(plugins_update)

        self.client.plugins_update.update_plugins('hello_world')

    def test_doesnt_raise_when_last_plugins_update_failed(self):
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update_id = self.client.plugins_update.update_plugins(
            'hello_world').id
        plugins_update = self.sm.get(models.PluginsUpdate, plugins_update_id)
        plugins_update.state = STATES.FAILED
        self.sm.update(plugins_update)

        self.client.plugins_update.update_plugins('hello_world')

    def test_doesnt_raise_when_last_plugins_update_didnt_do_anything(self):
        self.put_blueprint(blueprint_id='hello_world')
        self.client.deployments.create('hello_world', 'd123')
        self.wait_for_deployment_creation(self.client, 'd123')
        plugins_update_id = self.client.plugins_update.update_plugins(
            'hello_world').id
        plugins_update = self.sm.get(models.PluginsUpdate, plugins_update_id)
        plugins_update.state = STATES.NO_CHANGES_REQUIRED
        self.sm.update(plugins_update)

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
        plugins_update = self.sm.get(models.PluginsUpdate, plugins_update_id)
        plugins_update.state = STATES.SUCCESSFUL
        self.sm.update(plugins_update)
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
        blueprint = self.sm.get(models.Blueprint, 'hello_world')
        plan = deepcopy(blueprint.plan)
        plan[DEPLOYMENT_PLUGINS_TO_INSTALL].append('dummy')
        blueprint.plan = plan
        self.sm.update(blueprint)
        self.pretend_deployments_updated(plugins_update_id)
        # Sanity check
        self.assertIn(
            'dummy',
            self.sm.get(models.Blueprint, 'hello_world')
                .plan[DEPLOYMENT_PLUGINS_TO_INSTALL])
        self.client.plugins_update.finalize_plugins_update(
            plugins_update_id)
        self.assertNotIn(
            'dummy',
            self.sm.get(models.Blueprint, 'hello_world')
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
        self.sm.get(models.Blueprint, plugins_update.temp_blueprint_id)
        with self.assertRaises(CloudifyClientError):
            plugins_update = self.client.plugins_update.\
                finalize_plugins_update(plugins_update.id)
        with self.assertRaises(NotFoundError):
            self.sm.get(models.Blueprint, plugins_update.temp_blueprint_id)

    def test_finalize_error_if_deployments_not_updated(self):
        self.put_blueprint(blueprint_id='bp')
        self.client.deployments.create('bp', 'dep')
        self.wait_for_deployment_creation(self.client, 'dep')
        plugins_update = self.client.plugins_update.update_plugins('bp')
        self.sm.get(models.Blueprint, plugins_update.temp_blueprint_id)
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
        self.sm.get(models.Blueprint, plugins_update.temp_blueprint_id)
        with self.assertRaises(CloudifyClientError):
            plugins_update = self.client.plugins_update.\
                finalize_plugins_update(plugins_update.id)
        self.assertRegex(plugins_update['temp_blueprint_id'],
                         r'^plugins-update\-.*\-bp$')
        self.assertEmpty(self.sm.list(
            models.Deployment,
            filters={'blueprint_id': plugins_update['temp_blueprint_id']},
        ).items)
        updated_deployment = self.sm.get(
            models.Deployment,
            plugins_update.deployments_per_tenant[
                plugins_update.tenant_name][0]
        )
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
        dep1 = self.sm.get(models.Deployment, 'dep1')
        self.assertEqual(plugins_update.temp_blueprint_id, dep1.blueprint.id)
        # Check not update deployment
        dep2 = self.sm.get(models.Deployment, 'dep2')
        self.assertEqual(plugins_update.blueprint_id, dep2.blueprint.id)

    def pretend_deployments_updated(self, plugins_update_id: str,
                                    deployment_ids: list = None):
        """Pretend those deployments were updated."""
        plugins_update = self.sm.get(models.PluginsUpdate,
                                     plugins_update_id)
        temp_blueprint = self.sm.get(models.Blueprint,
                                     plugins_update.temp_blueprint.id)
        if deployment_ids is None:
            deployment_ids = plugins_update.deployments_to_update
        if deployment_ids is None:
            deployment_ids = plugins_update.deployments_per_tenant[
                plugins_update.tenant_name]
        for deployment_id in deployment_ids:
            deployment = self.sm.get(models.Deployment, deployment_id)
            deployment.blueprint = temp_blueprint
            self.sm.update(deployment)


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

#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import uuid
from unittest.mock import patch

from cloudify_rest_client import exceptions
from cloudify.models_states import BlueprintUploadState, ExecutionState

from manager_rest.storage import models
from manager_rest.test.base_test import BaseServerTestCase
from manager_rest.maintenance import (
    get_maintenance_state,
    remove_maintenance_state,
)
from manager_rest.constants import (
    MAINTENANCE_MODE_ACTIVATED,
    MAINTENANCE_MODE_ACTIVATING,
    MAINTENANCE_MODE_DEACTIVATED,
)


class MaintenanceModeTest(BaseServerTestCase):
    def tearDown(self):
        super(MaintenanceModeTest, self).tearDown()
        remove_maintenance_state()

    def test_maintenance_mode_inactive(self):
        response = self.client.maintenance_mode.status()
        self.assertEqual(MAINTENANCE_MODE_DEACTIVATED, response.status)
        self.assertFalse(response.activation_requested_at)
        self.client.blueprints.list()

    def test_maintenance_activation(self):
        response = self.client.maintenance_mode.activate()
        self.assertEqual(MAINTENANCE_MODE_ACTIVATED, response.status)

        # invocation of status goes through a different route.
        response = self.client.maintenance_mode.status()
        self.assertEqual(MAINTENANCE_MODE_ACTIVATED, response.status)

    def test_any_cmd_activates_maintenance_mode(self):
        execution = self._start_maintenance_transition_mode(
            bp_id='bp1',
            dep_id='dep1')
        self._terminate_execution(execution.id)
        self.assertRaises(exceptions.MaintenanceModeActiveError,
                          self.client.blueprints.upload,
                          self.get_mock_blueprint_path(),
                          'b1')
        self.client.maintenance_mode.deactivate()

        execution = self._start_maintenance_transition_mode(
            bp_id='bp2',
            dep_id='dep2')
        self._terminate_execution(execution.id)
        state = get_maintenance_state()
        self.assertEqual(state['status'], MAINTENANCE_MODE_ACTIVATING)
        self.client.manager.get_version()
        state = get_maintenance_state()
        self.assertEqual(state['status'], MAINTENANCE_MODE_ACTIVATED)

    def test_request_denial_in_maintenance_mode(self):
        self._activate_maintenance_mode()
        self.assertRaises(exceptions.MaintenanceModeActiveError,
                          self.client.blueprints.list)

    def test_request_approval_in_maintenance_mode(self):
        self._activate_maintenance_mode()

        self.client.maintenance_mode.status()
        self.client.manager.get_version()
        self.client.manager.get_status()

    def test_unauthorized_bypass_maintenance_denial_in_maintenance_mode(self):
        self._activate_maintenance_mode()

        internal_request_client = self.create_client(
            headers={'X-BYPASS-MAINTENANCE': 'true'})
        with patch('manager_rest.maintenance.is_user_action_allowed',
                   return_value=False):
            self.assertRaises(exceptions.MaintenanceModeActiveError,
                              internal_request_client.blueprints.list)

    def test_multiple_maintenance_mode_activations(self):
        self._activate_maintenance_mode()
        with self.assertRaises(exceptions.NotModifiedError) as cm:
            self._activate_maintenance_mode()
        self.assertEqual(304, cm.exception.status_code)

    def test_transition_to_active(self):
        execution = self._start_maintenance_transition_mode()
        response = self.client.maintenance_mode.status()
        self.assertEqual(response.status, MAINTENANCE_MODE_ACTIVATING)
        self._terminate_execution(execution.id)
        response = self.client.maintenance_mode.status()
        self.assertEqual(response.status, MAINTENANCE_MODE_ACTIVATED)

    def test_deployment_denial_in_maintenance_transition_mode(self):
        self._start_maintenance_transition_mode()
        self.client.blueprints.upload(self.get_mock_blueprint_path(), 'b1',
                                      async_upload=True)
        self.assertRaises(exceptions.MaintenanceModeActivatingError,
                          self.client.deployments.create,
                          blueprint_id='b1',
                          deployment_id='d1')

    def test_deployment_modification_denial_maintenance_transition_mode(self):
        self._start_maintenance_transition_mode()
        self.assertRaises(exceptions.MaintenanceModeActivatingError,
                          self.client.deployment_modifications.start,
                          deployment_id='d1',
                          nodes={})

    def test_snapshot_creation_denial_in_maintenance_transition_mode(self):
        self._start_maintenance_transition_mode()
        self.assertRaises(exceptions.MaintenanceModeActivatingError,
                          self.client.snapshots.create,
                          snapshot_id='s1',
                          include_credentials=False)

    def test_snapshot_restoration_denial_in_maintenance_transition_mode(self):
        self._start_maintenance_transition_mode()
        self.assertRaises(exceptions.MaintenanceModeActivatingError,
                          self.client.snapshots.restore,
                          snapshot_id='s1')

    def test_executions_denial_in_maintenance_transition_mode(self):
        self._start_maintenance_transition_mode()
        self.assertRaises(exceptions.MaintenanceModeActivatingError,
                          self.client.executions.start,
                          deployment_id='d1',
                          workflow_id='install')

    def test_request_approval_in_maintenance_transition_mode(self):
        self._start_maintenance_transition_mode()
        try:
            self.client.blueprints.list()
            self.client.manager.get_version()
        except exceptions.CloudifyClientError:
            self.fail('An allowed rest request failed while '
                      'activating maintenance mode.')

    def test_execution_amount_maintenance_activated(self):
        self._activate_maintenance_mode()
        response = self.client.maintenance_mode.status()
        self.assertFalse(response.remaining_executions)

    def test_execution_amount_maintenance_deactivated(self):
        self._activate_and_deactivate_maintenance_mode()
        response = self.client.maintenance_mode.status()
        self.assertFalse(response.remaining_executions)

    def test_execution_amount_maintenance_activating(self):
        execution = self._start_maintenance_transition_mode()
        response = self.client.maintenance_mode.status()
        self.assertEqual(1, len(response.remaining_executions))
        self.assertEqual(execution.id,
                         response.remaining_executions[0]['id'])
        self.assertEqual(execution.deployment_id,
                         response.remaining_executions[0]['deployment_id'])
        self.assertEqual(execution.workflow_id,
                         response.remaining_executions[0]['workflow_id'])
        self.assertEqual(ExecutionState.STARTED,
                         response.remaining_executions[0]['status'])

    def test_trigger_time_maintenance_activated(self):
        self._activate_maintenance_mode()
        response = self.client.maintenance_mode.status()
        self.assertTrue(response.activated_at)

    def test_trigger_time_maintenance_deactivated(self):
        self._activate_and_deactivate_maintenance_mode()
        response = self.client.maintenance_mode.status()
        self.assertFalse(response.activated_at)

    def test_trigger_time_maintenance_activating(self):
        self._start_maintenance_transition_mode()
        response = self.client.maintenance_mode.status()
        self.assertTrue(response.activation_requested_at)

    def test_deactivate_maintenance_mode(self):
        self._activate_maintenance_mode()
        response = self.client.maintenance_mode.deactivate()
        self.assertEqual(MAINTENANCE_MODE_DEACTIVATED, response.status)
        response = self.client.maintenance_mode.status()
        self.assertEqual(MAINTENANCE_MODE_DEACTIVATED, response.status)

    def test_request_approval_after_maintenance_mode_deactivation(self):
        self._activate_and_deactivate_maintenance_mode()
        bp = models.Blueprint(
            id='b1',
            creator=self.user,
            state=BlueprintUploadState.UPLOADED,
            plan={},
            tenant=self.tenant,
        )
        self.client.deployments.create(bp.id, 'd1')

    def test_multiple_maintenance_mode_deactivations(self):
        self._activate_and_deactivate_maintenance_mode()
        with self.assertRaises(exceptions.NotModifiedError) as cm:
            self.client.maintenance_mode.deactivate()
        self.assertEqual(304, cm.exception.status_code)

    def test_maintenance_mode_activated_error_raised(self):
        self._activate_maintenance_mode()
        self.assertRaises(exceptions.MaintenanceModeActiveError,
                          self.client.blueprints.list)

    def test_running_execution_maintenance_activating_error_raised(self):
        self._test_different_execution_status_in_activating_mode()

    def test_pending_execution_maintenance_activating_error_raised(self):
        self._test_different_execution_status_in_activating_mode(
            ExecutionState.PENDING)

    def test_cancelling_execution_maintenance_activating_error_raised(self):
        self._test_different_execution_status_in_activating_mode(
            ExecutionState.CANCELLING)

    def test_force_cancelling_execution_maintenance_activating_error_raised(
            self):
        self._test_different_execution_status_in_activating_mode(
            ExecutionState.FORCE_CANCELLING)

    def _test_different_execution_status_in_activating_mode(
            self,
            execution_status=ExecutionState.STARTED):
        bp = models.Blueprint(
            id='b1',
            creator=self.user,
            state=BlueprintUploadState.UPLOADED,
            plan={},
            tenant=self.tenant,
        )
        self._start_maintenance_transition_mode(
            execution_status=execution_status)
        self.assertRaises(exceptions.MaintenanceModeActivatingError,
                          self.client.deployments.create,
                          blueprint_id=bp.id,
                          deployment_id='d1')

    def _activate_maintenance_mode(self):
        self.client.maintenance_mode.activate()
        self.client.maintenance_mode.status()

    def _start_maintenance_transition_mode(
            self,
            bp_id='transition_blueprint',
            dep_id='transition_deployment',
            execution_status=ExecutionState.STARTED):
        bp = models.Blueprint(
            id=bp_id,
            creator=self.user,
            tenant=self.tenant,
        )
        dep = models.Deployment(
            id=dep_id,
            blueprint=bp,
            creator=self.user,
            tenant=self.tenant,
        )
        exc = models.Execution(
            id=str(uuid.uuid4()),
            deployment=dep,
            workflow_id='install',
            status=execution_status,
            creator=self.user,
            tenant=self.tenant,
        )
        self.client.maintenance_mode.activate()
        response = self.client.maintenance_mode.status()
        self.assertEqual(MAINTENANCE_MODE_ACTIVATING, response.status)

        return exc

    def _update_execution_status(self, execution_id, new_status, error=''):
        execution = self.sm.get(models.Execution, execution_id)
        execution.status = new_status
        execution.error = error
        self.sm.update(execution)

    def _terminate_execution(self, execution_id):
        self._update_execution_status(execution_id, ExecutionState.TERMINATED)

    def _activate_and_deactivate_maintenance_mode(self):
        self._activate_maintenance_mode()
        self.client.maintenance_mode.deactivate()

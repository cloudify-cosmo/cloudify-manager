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
import os
from nose.plugins.attrib import attr

from cloudify_rest_client import exceptions
from manager_rest.test import base_test
from base_test import BaseServerTestCase
from manager_rest import storage_manager, models
from manager_rest.resources_v2_1 import write_maintenance_state
from manager_rest.constants import (
    MAINTENANCE_MODE_ACTIVE,
    ACTIVATING_MAINTENANCE_MODE,
    NOT_IN_MAINTENANCE_MODE,
    MAINTENANCE_MODE_STATUS_FILE,
    ACTIVATING_MAINTENANCE_MODE_ERROR_CODE,
    MAINTENANCE_MODE_ACTIVE_ERROR_CODE)


@attr(client_min_version=2.1, client_max_version=base_test.LATEST_API_VERSION)
class MaintenanceModeTest(BaseServerTestCase):

    def test_maintenance_mode_inactive(self):
        response = self.client.maintenance_mode.status()
        self.assertEqual(NOT_IN_MAINTENANCE_MODE, response.status)
        self.client.blueprints.list()

    def test_maintenance_activation(self):
        response = self.client.maintenance_mode.activate()
        self.assertEqual(ACTIVATING_MAINTENANCE_MODE, response.status)
        response = self.client.maintenance_mode.status()
        self.assertEqual(MAINTENANCE_MODE_ACTIVE, response.status)

        # Second invocation of status goes through a different route.
        response = self.client.maintenance_mode.status()
        self.assertEqual(MAINTENANCE_MODE_ACTIVE, response.status)

    def test_request_denial_in_maintenance_mode(self):
        self._activate_maintenance_mode()
        try:
            self.client.blueprints.list()
            self.fail('Expected GET request to '
                      'fail while in maintenance mode.')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(503, e.status_code)
            self.assertEqual(MAINTENANCE_MODE_ACTIVE_ERROR_CODE, e.error_code)

    def test_request_approval_in_maintenance_mode(self):
        self._activate_maintenance_mode()

        self.client.maintenance_mode.status()
        self.client.manager.get_version()
        self.client.manager.get_status()

    def test_multiple_maintenance_mode_activations(self):
        self._activate_maintenance_mode()
        try:
            self._activate_maintenance_mode()
            self.fail('Expected the second start request to fail '
                      'since maintenance mode is already started.')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(304, e.status_code)

    def test_deployment_denial_in_maintenance_transition_mode(self):
        self._start_maintenance_transition_mode()
        self.client.blueprints.upload(
                self.get_mock_blueprint_path(),
                blueprint_id='b1')
        try:
            self.client.deployments.create('b1', 'd1')
            self.fail('Expected request to fail '
                      'while activating maintenance mode.')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(503, e.status_code)
            self.assertEqual(
                    ACTIVATING_MAINTENANCE_MODE_ERROR_CODE,
                    e.error_code)

    def test_deployment_modification_denial_maintenance_transition_mode(self):
        self._start_maintenance_transition_mode()
        try:
            self.client.deployment_modifications.start('d1', {})
            self.fail('Expected request to fail '
                      'while activating maintenance mode.')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(503, e.status_code)
            self.assertEqual(
                    ACTIVATING_MAINTENANCE_MODE_ERROR_CODE,
                    e.error_code)

    def test_snapshot_creation_denial_in_maintenance_transition_mode(self):
        self._start_maintenance_transition_mode()
        try:
            self.client.snapshots.create('s1', False, False)
            self.fail('Expected request to fail '
                      'while activating maintenance mode.')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(503, e.status_code)
            self.assertEqual(
                    ACTIVATING_MAINTENANCE_MODE_ERROR_CODE,
                    e.error_code)

    def test_snapshot_restoration_denial_in_maintenance_transition_mode(self):
        self._start_maintenance_transition_mode()
        try:
            self.client.snapshots.restore('s1')
            self.fail('Expected request to fail '
                      'while activating maintenance mode.')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(503, e.status_code)
            self.assertEqual(
                    ACTIVATING_MAINTENANCE_MODE_ERROR_CODE,
                    e.error_code)

    def test_executions_denial_in_maintenance_transition_mode(self):
        self._start_maintenance_transition_mode()
        self.client.blueprints.upload(
                self.get_mock_blueprint_path(),
                blueprint_id='b1')
        try:
            self.client.executions.start('d1', 'install')
            self.fail('Expected request to fail '
                      'while activating maintenance mode.')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(503, e.status_code)
            self.assertEqual(
                    ACTIVATING_MAINTENANCE_MODE_ERROR_CODE,
                    e.error_code)

    def test_request_approval_in_maintenance_transition_mode(self):
        self._start_maintenance_transition_mode()
        try:
            self.client.blueprints.list()
            self.client.manager.get_version()
        except exceptions.CloudifyClientError:
            self.fail('An allowed rest request failed while '
                      'activating maintenance mode.')

    def test_deactivate_maintenance_mode(self):
        self._activate_maintenance_mode()
        response = self.client.maintenance_mode.deactivate()
        self.assertEqual(NOT_IN_MAINTENANCE_MODE, response.status)
        response = self.client.maintenance_mode.status()
        self.assertEqual(NOT_IN_MAINTENANCE_MODE, response.status)

    def test_request_approval_after_maintenance_mode_deactivation(self):
        self._activate_and_deactivate_maintenance_mode()
        self.client.blueprints.upload(
                self.get_mock_blueprint_path(),
                blueprint_id='b1')
        self.client.deployments.create('b1', 'd1')

    def test_multiple_maintenance_mode_deactivations(self):
        self._activate_and_deactivate_maintenance_mode()
        try:
            self.client.maintenance_mode.deactivate()
            self.fail('Expected the second stop request to fail '
                      'since maintenance mode is not active.')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(304, e.status_code)

    def test_maintenance_file(self):
        maintenance_file = os.path.join(self.maintenance_mode_dir,
                                        MAINTENANCE_MODE_STATUS_FILE)

        self.assertFalse(os.path.isfile(maintenance_file))
        write_maintenance_state(ACTIVATING_MAINTENANCE_MODE)

        with open(maintenance_file, 'r') as f:
            status = f.read()
            self.assertEqual(status, ACTIVATING_MAINTENANCE_MODE)

        write_maintenance_state(MAINTENANCE_MODE_ACTIVE)
        with open(maintenance_file, 'r') as f:
            status = f.read()
        self.assertEqual(status, MAINTENANCE_MODE_ACTIVE)

    def test_maintenance_mode_active_error_raised(self):
        self._activate_maintenance_mode()
        self.assertRaises(exceptions.MaintenanceModeActiveError,
                          self.client.blueprints.list)

    def test_maintenance_mode_activating_error_raised(self):
        self.client.blueprints.upload(
                self.get_mock_blueprint_path(),
                blueprint_id='b1')
        self._start_maintenance_transition_mode()
        self.assertRaises(exceptions.MaintenanceModeActivatingError,
                          self.client.deployments.create,
                          blueprint_id='b1',
                          deployment_id='d1')

    def _activate_maintenance_mode(self):
        self.client.maintenance_mode.activate()
        self.client.maintenance_mode.status()

    def _start_maintenance_transition_mode(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment('d1')
        execution = self.client.executions.start(deployment_id, 'install')
        execution = self.client.executions.get(execution.id)
        self.assertEquals('terminated', execution.status)
        storage_manager._get_instance().update_execution_status(
                execution.id, models.Execution.STARTED, error='')

        self.client.maintenance_mode.activate()
        response = self.client.maintenance_mode.status()
        self.assertEqual(ACTIVATING_MAINTENANCE_MODE, response.status)

    def _activate_and_deactivate_maintenance_mode(self):
        self._activate_maintenance_mode()
        self.client.maintenance_mode.deactivate()

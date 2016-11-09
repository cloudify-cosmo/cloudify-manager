########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
#

from manager_rest.storage.models_states import ExecutionState

from cloudify_rest_client.exceptions import CloudifyClientError

from .security_base import TestAuthenticationBase
from integration_tests.tests.utils import get_resource as resource

RUNNING_EXECUTIONS_MESSAGE = 'There are running executions for this deployment'


class AuthorizationTest(TestAuthenticationBase):

    admin_username = 'alice'
    admin_password = 'alice_password'
    default_username = 'bob'
    default_password = 'bob_password'
    suspended_username = 'clair'
    suspended_password = 'clair_password'

    blueprint1_id = 'blueprint1_id'
    blueprint2_id = 'blueprint2_id'
    blueprint3_id = 'blueprint3_id'

    deployment1_id = 'deployment1_id'
    deployment2_id = 'deployment2_id'
    deployment3_id = 'deployment3_id'

    def test_authorization(self):
        self._assert_blueprint_operations()
        self._assert_deployment_operations()
        self._assert_execution_operations()

    def _assert_blueprint_operations(self):
        self._assert_upload_blueprint()
        self._assert_list_blueprint()
        self._assert_get_blueprint()
        self._assert_delete_blueprint()

    def _assert_deployment_operations(self):
        self._assert_create_deployment()
        self._assert_list_deployment()
        self._assert_delete_deployment()

    def _assert_execution_operations(self):
        self._assert_start_execution()
        execution_ids = [e.id for e in self.client.executions.list()]
        execution_id = execution_ids[0]
        self._assert_list_executions(execution_ids)
        self._assert_get_execution(execution_id)
        self._assert_cancel_execution(execution_id)

    def _assert_upload_blueprint(self):
        blueprint_path = resource('dsl/empty_blueprint.yaml')

        # admins and default users should be able to upload blueprints...
        with self._login_client(username=self.admin_username,
                                password=self.admin_password):
            self.client.blueprints.upload(blueprint_path, self.blueprint1_id)
            self.client.blueprints.upload(blueprint_path, self.blueprint2_id)

        with self._login_client(username=self.default_username,
                                password=self.default_password):
            self.client.blueprints.upload(blueprint_path, self.blueprint3_id)

        # ...but suspended users should not
        with self._login_client(username=self.suspended_username,
                                password=self.suspended_password):
            self._assert_unauthorized(self.client.blueprints.upload,
                                      blueprint_path, blueprint_id='dummy_bp')

    def _wait_for_deployment_executions(self, deployment_id):
        executions = self.client.executions.list(deployment_id=deployment_id)
        executions = [e for e in executions
                      if e.status not in ExecutionState.END_STATES]
        if executions:
            self.wait_for_execution_to_end(executions[0])

    def _assert_list_blueprint(self):
        def _list_and_assert():
            bp_ids = [bp.id for bp in self.client.blueprints.list()]
            for blueprint_id in (self.blueprint1_id,
                                 self.blueprint2_id,
                                 self.blueprint3_id):
                self.assertIn(blueprint_id, bp_ids)

        # admins and default users should be able to list blueprints...
        with self._login_client(username=self.admin_username,
                                password=self.admin_password):
            _list_and_assert()

        with self._login_client(username=self.default_username,
                                password=self.default_password):
            _list_and_assert()

        # ...but suspended users should not
        with self._login_client(username=self.suspended_username,
                                password=self.suspended_password):
            self._assert_unauthorized(self.client.blueprints.list)

    def _assert_get_blueprint(self):
        # admins and default users should be able to get blueprints...
        with self._login_client(username=self.admin_username,
                                password=self.admin_password):
            self.client.blueprints.get(self.blueprint1_id)

        with self._login_client(username=self.default_username,
                                password=self.default_password):
            self.client.blueprints.get(self.blueprint1_id)

        # ...but suspended users should not
        with self._login_client(username=self.suspended_username,
                                password=self.suspended_password):
            self._assert_unauthorized(self.client.blueprints.get,
                                      self.blueprint1_id)

    def _assert_delete_blueprint(self):
        # admins and default users should be able to delete blueprints...
        with self._login_client(username=self.admin_username,
                                password=self.admin_password):
            self.client.blueprints.delete(self.blueprint2_id)

        with self._login_client(username=self.default_username,
                                password=self.default_password):
            self.client.blueprints.delete(self.blueprint3_id)

        # ...but suspended users should not
        with self._login_client(username=self.suspended_username,
                                password=self.suspended_password):
            self._assert_unauthorized(self.client.blueprints.delete,
                                      'dummy_bp')

    def _assert_create_deployment(self):
        # admins and default users should be able to create deployments...
        with self._login_client(username=self.admin_username,
                                password=self.admin_password):
            self.client.deployments.create(blueprint_id=self.blueprint1_id,
                                           deployment_id=self.deployment1_id)
            self.client.deployments.create(blueprint_id=self.blueprint1_id,
                                           deployment_id=self.deployment2_id)

        with self._login_client(username=self.default_username,
                                password=self.default_password):
            self.client.deployments.create(blueprint_id=self.blueprint1_id,
                                           deployment_id=self.deployment3_id)

        # ...but suspended users should not
        with self._login_client(username=self.suspended_username,
                                password=self.suspended_password):
            self._assert_unauthorized(self.client.deployments.create,
                                      blueprint_id=self.blueprint1_id,
                                      deployment_id='dummy_dp')

    def _assert_list_deployment(self):
        def _list_and_assert():
            dep_ids = [dep.id for dep in self.client.deployments.list()]
            for deployment_id in (self.deployment1_id,
                                  self.deployment2_id,
                                  self.deployment3_id):
                self.assertIn(deployment_id, dep_ids)

        # admins and default users should be able to list
        # deployments...
        with self._login_client(username=self.admin_username,
                                password=self.admin_password):
            _list_and_assert()

        with self._login_client(username=self.default_username,
                                password=self.default_password):
            _list_and_assert()

        # ...but suspended users should not
        with self._login_client(username=self.suspended_username,
                                password=self.suspended_password):
            self._assert_unauthorized(self.client.deployments.list)

    def _assert_delete_deployment(self):
        # admins and default users should be able to delete deployments...
        with self._login_client(username=self.admin_username,
                                password=self.admin_password):
            self._wait_for_deployment_executions(self.deployment2_id)
            self.client.deployments.delete(self.deployment2_id)

        with self._login_client(username=self.default_username,
                                password=self.default_password):
            self._wait_for_deployment_executions(self.deployment3_id)
            self.client.deployments.delete(self.deployment3_id)

        # ...but suspended users should not
        with self._login_client(username=self.suspended_username,
                                password=self.suspended_password):
            self._assert_unauthorized(self.client.deployments.delete,
                                      'dummy_dp')

    def _assert_start_execution(self):
        workflow = 'install'

        # admins and default users should be able to start executions...
        with self._login_client(username=self.admin_username,
                                password=self.admin_password):
            self.client.executions.start(self.deployment1_id, workflow)

        with self._login_client(username=self.default_username,
                                password=self.default_password):
            self._wait_for_deployment_executions(self.deployment1_id)
            self.client.executions.start(self.deployment1_id, workflow)

        # ...but suspended users should not
        with self._login_client(username=self.suspended_username,
                                password=self.suspended_password):
            self._assert_unauthorized(self.client.executions.start, 'dummy_dp',
                                      workflow)

    def _assert_list_executions(self, execution_ids):
        def _list_and_assert():
            ex_ids = [ex.id for ex in self.client.executions.list()]
            for execution_id in execution_ids:
                self.assertIn(execution_id, ex_ids)

        # admins and default users should be able so
        # list executions...
        with self._login_client(username=self.admin_username,
                                password=self.admin_password):
            _list_and_assert()

        with self._login_client(username=self.default_username,
                                password=self.default_password):
            _list_and_assert()

        # ...but suspended users should not
        with self._login_client(username=self.suspended_username,
                                password=self.suspended_password):
            self._assert_unauthorized(self.client.executions.list)

    def _assert_get_execution(self, execution_id):
        def _get_and_assert():
            execution = self.client.executions.get(execution_id)
            self.assertEqual(execution_id, execution.id)

        # admins and default users should be able to get executions...
        with self._login_client(username=self.admin_username,
                                password=self.admin_password):
            _get_and_assert()

        with self._login_client(username=self.default_username,
                                password=self.default_password):
            _get_and_assert()

        # ...but suspended users should not
        with self._login_client(username=self.suspended_username,
                                password=self.suspended_password):
            self._assert_unauthorized(self.client.executions.get, execution_id)

    def _assert_cancel_execution(self, execution_id):
        def _cancel_and_assert():
            # In this case, either option is ok, cancel or can't cancel
            # due to already terminated. important thing is no auth error
            try:
                self.client.executions.cancel(execution_id)
            except CloudifyClientError as e:
                self.assertIn('in status terminated', str(e))

        # admins and default users should be able to cancel executions...
        with self._login_client(username=self.admin_username,
                                password=self.admin_password):
            _cancel_and_assert()

        with self._login_client(username=self.default_username,
                                password=self.default_password):
            _cancel_and_assert()

        # ...but suspended users should not

        with self._login_client(username=self.suspended_username,
                                password=self.suspended_password):
            self._assert_unauthorized(self.client.executions.cancel,
                                      execution_id)

    def _assert_unauthorized(self, method, *args, **kwargs):
        with self.assertRaises(CloudifyClientError) as cm:
            method(*args, **kwargs)
        self.assertIn('401: User unauthorized', str(cm.exception))

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

import sh
import os
from contextlib import contextmanager

from .security_base import TestSecuredRestBase

from integration_tests.tests.utils import get_resource as resource

RUNNING_EXECUTIONS_MESSAGE = 'There are running executions for this deployment'


class AuthorizationTest(TestSecuredRestBase):

    admin_username = 'alice'
    admin_password = 'alice_password'
    default_username = 'bob'
    default_password = 'bob_password'
    viewer_username = 'clair'
    viewer_password = 'clair_password'
    suspended_username = 'dave'
    suspended_password = 'dave_password'

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
        with self._login_cli(self.admin_username, self.admin_password):
            self.cfy.blueprints.upload(blueprint_path,
                                       blueprint_id=self.blueprint1_id)
            self.cfy.blueprints.upload(blueprint_path,
                                       blueprint_id=self.blueprint2_id)

        with self._login_cli(self.default_username, self.default_password):
            self.cfy.blueprints.upload(blueprint_path,
                                       blueprint_id=self.blueprint3_id)

        # ...but viewers and suspended users should not
        with self._login_cli(self.viewer_username, self.viewer_password):
            self._assert_unauthorized(self.cfy.blueprints.upload,
                                      blueprint_path, blueprint_id='dummy_bp')

        with self._login_cli(self.suspended_username, self.suspended_password):
            self._assert_unauthorized(self.cfy.blueprints.upload,
                                      blueprint_path, blueprint_id='dummy_bp')

    def _assert_list_blueprint(self):
        def _list_and_assert():
            output = self.cfy.blueprints.list()
            for blueprint_id in (self.blueprint1_id,
                                 self.blueprint2_id,
                                 self.blueprint3_id):
                self.assertIn(blueprint_id, output)

        # admins, default users and viewers should be able to list
        # blueprints...
        with self._login_cli(self.admin_username, self.admin_password):
            _list_and_assert()

        with self._login_cli(self.default_username, self.default_password):
            _list_and_assert()

        with self._login_cli(self.viewer_username, self.viewer_password):
            _list_and_assert()

        # ...but suspended users should not
        with self._login_cli(self.suspended_username, self.suspended_password):
            self._assert_unauthorized(self.cfy.blueprints.list)

    def _assert_get_blueprint(self):
        # admins, default users and viewers should be able to get blueprints...
        with self._login_cli(self.admin_username, self.admin_password):
            self.cfy.blueprints.get(self.blueprint1_id)

        with self._login_cli(self.default_username, self.default_password):
            self.cfy.blueprints.get(self.blueprint1_id)

        with self._login_cli(self.viewer_username, self.viewer_password):
            self.cfy.blueprints.get(self.blueprint1_id)

        # ...but suspended users should not
        with self._login_cli(self.suspended_username, self.suspended_password):
            self._assert_unauthorized(self.cfy.blueprints.get,
                                      self.blueprint1_id)

    def _assert_delete_blueprint(self):
        # admins and default users should be able to delete blueprints...
        with self._login_cli(self.admin_username, self.admin_password):
            self.cfy.blueprints.delete(self.blueprint2_id)

        with self._login_cli(self.default_username, self.default_password):
            self.cfy.blueprints.delete(self.blueprint3_id)

        # ...but viewers and suspended users should not
        with self._login_cli(self.viewer_username, self.viewer_password):
            self._assert_unauthorized(self.cfy.blueprints.delete, 'dummy_bp')

        with self._login_cli(self.suspended_username, self.suspended_password):
            self._assert_unauthorized(self.cfy.blueprints.delete, 'dummy_bp')

    def _assert_create_deployment(self):
        # admins and default users should be able to create deployments...
        with self._login_cli(self.admin_username, self.admin_password):
            self.cfy.deployments.create(self.deployment1_id,
                                        blueprint_id=self.blueprint1_id)
            self.cfy.deployments.create(self.deployment2_id,
                                        blueprint_id=self.blueprint1_id)

        with self._login_cli(self.default_username, self.default_password):
            self.cfy.deployments.create(self.deployment3_id,
                                        blueprint_id=self.blueprint1_id)

        # ...but viewers and suspended users should not
        with self._login_cli(self.viewer_username, self.viewer_password):
            self._assert_unauthorized(self.cfy.deployments.create, 'dummy_dp',
                                      blueprint_id=self.blueprint1_id)

        with self._login_cli(self.suspended_username, self.suspended_password):
            self._assert_unauthorized(self.cfy.deployments.create, 'dummy_dp',
                                      blueprint_id=self.blueprint1_id)

    def _assert_list_deployment(self):
        def _list_and_assert():
            output = self.cfy.deployments.list()
            for deployment_id in (self.deployment1_id,
                                  self.deployment2_id,
                                  self.deployment3_id):
                self.assertIn(deployment_id, output)

        # admins, default users and viewers should be able to list
        # deployments...
        with self._login_cli(self.admin_username, self.admin_password):
            _list_and_assert()

        with self._login_cli(self.default_username, self.default_password):
            _list_and_assert()

        with self._login_cli(self.viewer_username, self.viewer_password):
            _list_and_assert()

        # ...but suspended users should not
        with self._login_cli(self.suspended_username, self.suspended_password):
            self._assert_unauthorized(self.cfy.deployments.list)

    def _assert_delete_deployment(self):
        # admins and default users should be able to delete deployments...
        with self._login_cli(self.admin_username, self.admin_password):
            self.cfy.deployments.delete(self.deployment2_id)

        with self._login_cli(self.default_username, self.default_password):
            self.cfy.deployments.delete(self.deployment3_id)

        # ...but viewers and suspended users should not
        with self._login_cli(self.viewer_username, self.viewer_password):
            self._assert_unauthorized(self.cfy.deployments.delete, 'dummy_dp')

        with self._login_cli(self.suspended_username, self.suspended_password):
            self._assert_unauthorized(self.cfy.deployments.delete, 'dummy_dp')

    def _assert_start_execution(self):
        workflow = 'install'

        # admins and default users should be able to start executions...
        with self._login_cli(self.admin_username, self.admin_password):
            self.cfy.executions.start(workflow,
                                      deployment_id=self.deployment1_id)

        with self._login_cli(self.default_username, self.default_password):
            self.cfy.executions.start(workflow,
                                      deployment_id=self.deployment1_id)

        # ...but viewers and suspended users should not
        with self._login_cli(self.viewer_username, self.viewer_password):
            self._assert_unauthorized(self.cfy.executions.start, workflow,
                                      deployment_id='dummy_dp')

        with self._login_cli(self.suspended_username, self.suspended_password):
            self._assert_unauthorized(self.cfy.executions.start, workflow,
                                      deployment_id='dummy_dp')

    def _assert_list_executions(self, execution_ids):
        def _list_and_assert():
            output = self.cfy.executions.list()
            for execution_id in execution_ids:
                self.assertIn(execution_id, output)

        # admins, default users and viewers should be able so
        # list executions...
        with self._login_cli(self.admin_username, self.admin_password):
            _list_and_assert()

        with self._login_cli(self.default_username, self.default_password):
            _list_and_assert()

        with self._login_cli(self.viewer_username, self.viewer_password):
            _list_and_assert()

        # ...but suspended users should not
        with self._login_cli(self.suspended_username, self.suspended_password):
            self._assert_unauthorized(self.cfy.executions.list)

    def _assert_get_execution(self, execution_id):
        def _get_and_assert():
            output = self.cfy.executions.get(execution_id)
            self.assertIn(execution_id, output)

        # admins, default users and viewers should be able to get executions...
        with self._login_cli(self.admin_username, self.admin_password):
            _get_and_assert()

        with self._login_cli(self.default_username, self.default_password):
            _get_and_assert()

        with self._login_cli(self.viewer_username, self.viewer_password):
            _get_and_assert()

        # ...but suspended users should not
        with self._login_cli(self.suspended_username, self.suspended_password):
            self._assert_unauthorized(self.cfy.executions.get, execution_id)

    def _assert_cancel_execution(self, execution_id):
        def _cancel_and_assert():
            # In this case, either option is ok, cancel or can't cancel
            # due to already terminated. important thing is no auth error
            try:
                self.cfy.executions.cancel(execution_id)
            except sh.ErrorReturnCode as e:
                self.assertIn('in status terminated', e.stdout)

        # admins and default users should be able to cancel executions...
        with self._login_cli(self.admin_username, self.admin_password):
            _cancel_and_assert()

        with self._login_cli(self.default_username, self.default_password):
            _cancel_and_assert()

        # ...but viewers and suspended users should not
        with self._login_cli(self.viewer_username, self.viewer_password):
            self._assert_unauthorized(self.cfy.executions.cancel,
                                      execution_id)

        with self._login_cli(self.suspended_username, self.suspended_password):
            self._assert_unauthorized(self.cfy.executions.cancel,
                                      execution_id)

    def _assert_unauthorized(self, method, *args, **kwargs):
        with self.assertRaises(sh.ErrorReturnCode) as c:
            method(*args, **kwargs)
        self.assertIn('401: User unauthorized', c.exception.stdout)

    @contextmanager
    def _login_cli(self, username=None, password=None):
        self.logger.info('Logging in with username: {0}, '
                         'password: {1}'.format(username, password))
        prev_username = os.environ.get('CLOUDIFY_USERNAME')
        prev_password = os.environ.get('CLOUDIFY_PASSWORD')
        try:
            os.environ['CLOUDIFY_USERNAME'] = username
            os.environ['CLOUDIFY_PASSWORD'] = password
            yield
        finally:
            if prev_username:
                os.environ['CLOUDIFY_USERNAME'] = prev_username
            else:
                os.environ.pop('CLOUDIFY_USERNAME')
            if prev_password:
                os.environ['CLOUDIFY_PASSWORD'] = prev_password
            else:
                os.environ.pop('CLOUDIFY_PASSWORD')

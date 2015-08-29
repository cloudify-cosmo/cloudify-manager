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

from nose.plugins.attrib import attr

from manager_rest.test import base_test
from manager_rest.test.security.security_test_base import SecurityTestBase
from cloudify_rest_client.exceptions import UserUnauthorizedError


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class AuthorizationTests(SecurityTestBase):

    def test_admin_access(self):
        client = self.create_client(
            headers=SecurityTestBase.create_auth_header(
                username='alice', password='alice_password'))   # administrator
        # admins should be able to do everything
        client.deployments.list()

    def test_manager_access(self):
        client = self.create_client(
            headers=SecurityTestBase.create_auth_header(
                username='bob', password='bob_password'))   # manager
        # deployment_managers should be able to do deploy and un-deploy
        # to list blueprints, deployment and executions
        # deployment_manager should not be able to assign roles
        client.deployments.list()

    def test_viewer_access(self):
        client = self.create_client(
            headers=SecurityTestBase.create_auth_header(
                username='carol', password='carol_password'))   # viewer
        # viewers should be able to do viewer all resources but not create
        # or delete resources
        client.deployments.list()
        self.assertRaises(UserUnauthorizedError, client.blueprints.delete,
                          'dummy_blueprint_id')

    def test_user_access(self):
        client = self.create_client(
            headers=SecurityTestBase.create_auth_header(
                username='dave', password='dave_password'))     # user
        # users should not be able to do anything
        self.assertRaises(UserUnauthorizedError, client.deployments.list)

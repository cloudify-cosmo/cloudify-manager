########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import uuid

import requests
import requests.status_codes
from requests.exceptions import ConnectionError

from manager_rest.constants import USER_ROLE, CLOUDIFY_TENANT_HEADER
from cloudify_cli.env import get_auth_header

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    create_rest_client, get_resource as resource)


class ResourcesAvailableTest(AgentlessTestCase):

    def test_resources_available(self):
        container_ip = self.get_manager_ip()
        blueprint_id = str(uuid.uuid4())
        blueprint_name = 'empty_blueprint.yaml'
        blueprint_path = resource('dsl/{0}'.format(blueprint_name))
        self.client.blueprints.upload(blueprint_path,
                                      blueprint_id=blueprint_id)
        invalid_resource_url = 'http://{0}/resources/blueprints/{1}/{2}' \
            .format(container_ip, blueprint_id, blueprint_name)
        try:
            result = requests.head(invalid_resource_url)
            self.assertEqual(
                result.status_code, requests.status_codes.codes.not_found,
                "Resources are available through a different port than 53229.")
        except ConnectionError:
            pass

    def test_resources_access(self):
        self.client.blueprints.upload(resource('dsl/empty_blueprint.yaml'),
                                      blueprint_id='blu')
        self.client.users.create(username='u', password='p', role=USER_ROLE)
        self.client.tenants.create(tenant_name='t')
        self.client.tenants.add_user(username='u', tenant_name='t')
        tenant_t_client = create_rest_client(tenant='t')
        tenant_t_client.blueprints.upload(resource('dsl/empty_blueprint.yaml'),
                                          blueprint_id='blu')

        # admin can access both blueprints
        admin_headers = self.client._client.headers
        self._assert_request_status_code(
            headers=admin_headers,
            path='/blueprints/default_tenant/blu/empty_blueprint.yaml',
            expected_status_code=requests.status_codes.codes.ok)

        admin_headers[CLOUDIFY_TENANT_HEADER] = 't'
        self._assert_request_status_code(
            headers=admin_headers,
            path='/blueprints/t/blu/empty_blueprint.yaml',
            expected_status_code=requests.status_codes.codes.ok)

        # user u can only access blueprints in tenant t
        user_headers = get_auth_header('u', 'p')
        user_headers[CLOUDIFY_TENANT_HEADER] = 't'
        # valid access
        self._assert_request_status_code(
            headers=user_headers,
            path='/blueprints/t/blu/empty_blueprint.yaml',
            expected_status_code=requests.status_codes.codes.ok)
        # invalid - trying to access unauthorized tenant
        self._assert_request_status_code(
            headers=user_headers,
            path='/blueprints/default_tenant/blu/empty_blueprint.yaml',
            expected_status_code=requests.status_codes.codes.unauthorized)
        # invalid - trying to authenticate with wrong tenant
        user_headers[CLOUDIFY_TENANT_HEADER] = 'default_tenant'
        self._assert_request_status_code(
            headers=user_headers,
            path='/blueprints/t/blu/empty_blueprint.yaml',
            expected_status_code=requests.status_codes.codes.unauthorized)
        self._assert_request_status_code(
            headers=user_headers,
            path='/blueprints/default_tenant/blu/empty_blueprint.yaml',
            expected_status_code=requests.status_codes.codes.unauthorized)

        # trying to access non-existing resource
        self._assert_request_status_code(
            headers=admin_headers,
            path='/blueprints/t/blu/fake_resource_that_does_not_exist',
            expected_status_code=requests.status_codes.codes.not_found)

    def _assert_request_status_code(self,
                                    headers,
                                    path,
                                    expected_status_code):
        self.assertEquals(
            expected_status_code,
            requests.get(
                'http://{0}:53229{1}'.format(self.get_manager_ip(), path),
                headers=headers
            ).status_code
        )

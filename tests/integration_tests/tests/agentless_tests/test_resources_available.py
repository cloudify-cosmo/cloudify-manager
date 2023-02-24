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
import pytest

import requests
import requests.status_codes
from requests.exceptions import ConnectionError

from cloudify.utils import ipv6_url_compat

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    get_resource as resource,
    wait_for_blueprint_upload,
)
from integration_tests.framework.utils import create_auth_header


pytestmark = pytest.mark.group_general


class ResourcesAvailableTest(AgentlessTestCase):

    def test_resources_available(self):
        container_ip = self.env.address
        blueprint_id = 'b{0}'.format(uuid.uuid4())
        blueprint_name = 'empty_blueprint.yaml'
        blueprint_path = resource('dsl/{0}'.format(blueprint_name))
        self.client.blueprints.upload(blueprint_path,
                                      entity_id=blueprint_id)
        invalid_resource_url = 'https://{0}:{1}/resources/blueprints/{1}/{2}' \
            .format(ipv6_url_compat(container_ip), 53229, blueprint_id)
        try:
            result = requests.head(invalid_resource_url)
            self.assertEqual(
                result.status_code, requests.status_codes.codes.not_found,
                "Resources are available through port 53229.")
        except ConnectionError:
            pass

    def test_resources_access(self):
        self.client.blueprints.upload(resource('dsl/empty_blueprint.yaml'),
                                      entity_id='blu')
        wait_for_blueprint_upload('blu', self.client)

        # admin can the blueprint
        admin_headers = self.client._client.headers
        self._assert_request_status_code(
            headers=admin_headers,
            path='/blueprints/default_tenant/blu/empty_blueprint.yaml',
            expected_status_code=requests.status_codes.codes.ok)

        # invalid authentication
        self._assert_request_status_code(
            headers=create_auth_header('bla', 'bla'),
            path='/blueprints/default_tenant/blu/empty_blueprint.yaml',
            expected_status_code=requests.status_codes.codes.unauthorized)

        # trying to access non-existing resource
        self._assert_request_status_code(
            headers=admin_headers,
            path='/blueprints/default_tenant/blu/non_existing_resource',
            expected_status_code=requests.status_codes.codes.not_found)

    def _assert_request_status_code(self,
                                    headers,
                                    path,
                                    expected_status_code):
        self.assertEqual(
            expected_status_code,
            requests.get(
                'https://{0}:443/resources{1}'.format(
                    ipv6_url_compat(self.env.address), path),
                headers=headers,
                verify=False
            ).status_code
        )

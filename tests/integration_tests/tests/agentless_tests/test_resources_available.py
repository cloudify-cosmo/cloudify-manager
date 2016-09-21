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

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource


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

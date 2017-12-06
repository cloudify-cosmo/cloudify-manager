#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
from cloudify_rest_client.exceptions import CloudifyClientError

from . import common


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class ARIAServiceTemplateTestCase(base_test.BaseServerTestCase):

    def test_get_empty(self):
        result = self.client.aria_service_templates.list()
        self.assertEquals(0, len(result))

    def test_get_nonexistent_service_template(self):
        try:
            self.client.aria_service_templates.get('15')
        except CloudifyClientError, e:
            self.assertEqual(404, e.status_code)

    def test_upload_service_template(self):
        common.upload_service_template(
            self.client,
            common.get_service_template('single-node.yaml'),
            'hello'
        )

        service_templates = self.client.aria_service_templates.list(
            name='hello'
        )
        self.assertEqual(1, len(service_templates))
        service_template = service_templates[0]
        self.assertEqual('hello', service_template.name)

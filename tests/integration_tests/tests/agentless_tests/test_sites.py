########
# Copyright (c) 2020 GigaSpaces Technologies Ltd. All rights reserved
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

from integration_tests import AgentlessTestCase

from cloudify.models_states import VisibilityState
from cloudify_rest_client.exceptions import CloudifyClientError


class TestSites(AgentlessTestCase):
    def test_site_creation(self):
        """Create a single site."""
        self.client.sites.create('test_site')
        site = self.client.sites.get('test_site')
        self.assertEqual(site.name, 'test_site')
        self.assertEqual(site.visibility, VisibilityState.TENANT)

    def test_name_modification(self):
        """Create site and modify its name."""
        self.client.sites.create('test_site')

        # Test the modification
        self.client.sites.update('test_site', new_name='new_site')
        site = self.client.sites.get('new_site')
        self.assertEqual(site.name, 'new_site')
        self.assertEqual(site.visibility, VisibilityState.TENANT)

        # Verify that the old name is inaccessible
        error_msg = r"404.+Site.+`test_site`.+not found"
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.sites.get,
                               'test_site')

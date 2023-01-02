#########
# Copyright (c) 2013-2019 Cloudify Platform Ltd. All rights reserved
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

from manager_rest import utils
from manager_rest.test import base_test
from manager_rest.storage import models

from cloudify.models_states import VisibilityState
from cloudify_rest_client.exceptions import CloudifyClientError


class SitesTestCase(base_test.BaseServerTestCase):

    def _put_site(self, name='test_site'):
        site = models.Site(
            id=name,
            name=name,
            latitude=42,
            longitude=43,
            visibility=VisibilityState.TENANT,
            created_at=utils.get_formatted_timestamp(),
            creator=self.user,
            tenant=self.tenant,
        )
        self.sm.put(site)

    def _create_sites(self, sites_number):
        for i in range(1, sites_number + 1):
            self._put_site('test_site_{}'.format(i))

    def _test_invalid_location(self, sites_command):
        error_msg = '400: Invalid location `34.787274`, the format is ' \
                    'expected to be "latitude,longitude" such as ' \
                    '"32.071072,34.787274"'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               sites_command,
                               'test_site',
                               location='34.787274')

        error_msg = '400: Invalid location `lat,long`, the latitude and ' \
                    'longitude are expected to be of type float'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               sites_command,
                               'test_site',
                               location='lat,long')

        error_msg = '400: Invalid location `200,32.071072`. The latitude ' \
                    'must be a number between -90 and 90 and the longitude ' \
                    'between -180 and 180'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               sites_command,
                               'test_site',
                               location='200,32.071072')

        error_msg = '400: Invalid location `32.071072,200`. The latitude ' \
                    'must be a number between -90 and 90 and the longitude ' \
                    'between -180 and 180'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               sites_command,
                               'test_site',
                               location='32.071072,200')

    def test_get_site(self):
        self._put_site()
        result = self.client.sites.get('test_site')
        expected = {
            'name': 'test_site',
            'location': '42.0, 43.0',
            'visibility': VisibilityState.TENANT
        }
        actual = {k: result[k] for k in expected}
        self.assertEqual(actual, expected)

    def test_get_site_not_found(self):
        error_msg = "404: Requested `Site` with ID `my_site` was not found"
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.sites.get,
                               'my_site')

    def test_list_sites(self):
        self._create_sites(sites_number=3)
        sites = self.client.sites.list()
        self.assertEqual(len(sites), 3)
        for i in range(1, 4):
            self.assertEqual(sites[i - 1].name, 'test_site_{}'.format(i))

    def test_list_sites_empty(self):
        sites = self.client.sites.list()
        self.assertEqual(len(sites), 0)

    def test_list_sites_sort(self):
        self._create_sites(sites_number=3)
        sites = self.client.sites.list(sort='created_at')
        self.assertEqual(len(sites), 3)

        for i in range(1, 4):
            self.assertEqual(sites[i - 1].name, 'test_site_{}'.format(i))

        sites = self.client.sites.list(sort='created_at', is_descending=True)
        self.assertEqual(len(sites), 3)

        for i in range(1, 4):
            self.assertEqual(sites[i - 1].name, 'test_site_{}'.format(4 - i))

    def test_list_sites_filter(self):
        self._create_sites(sites_number=3)
        sites = self.client.sites.list(name='my_site')
        self.assertEqual(len(sites), 0)

        sites = self.client.sites.list(name=['test_site_1', 'test_site_3'])
        self.assertEqual(len(sites), 2)

    def test_list_sites_include(self):
        self._put_site()
        sites = self.client.sites.list(_include=['name'])
        self.assertEqual(sites[0].name, 'test_site')
        self.assertIsNone(sites[0].visibility)
        self.assertIsNone(sites[0].location)

    def test_create_site(self):
        self.client.sites.create('test_site', location='34.787274,32.071072')
        site = self.client.sites.get('test_site')
        self.assertEqual(site.name, 'test_site')
        self.assertEqual(site.location, '34.787274, 32.071072')
        self.assertEqual(site.visibility, VisibilityState.TENANT)

    def test_create_site_edge_location(self):
        self.client.sites.create('test_site_1', location='0,0')
        site = self.client.sites.get('test_site_1')
        self.assertEqual(site.location, '0.0, 0.0')

        self.client.sites.create('test_site_2', location='-0,-0')
        site = self.client.sites.get('test_site_2')
        self.assertEqual(site.location, '0.0, 0.0')

        self.client.sites.create('test_site_3',
                                 location='89.999999,179.999999')
        site = self.client.sites.get('test_site_3')
        self.assertEqual(site.location, '89.999999, 179.999999')

        self.client.sites.create('test_site_4',
                                 location='-89.999999,-179.999999')
        site = self.client.sites.get('test_site_4')
        self.assertEqual(site.location, '-89.999999, -179.999999')

        # Location with space
        self.client.sites.create('test_site_5',
                                 location='32.166369, 34.810893')
        site = self.client.sites.get('test_site_5')
        self.assertEqual(site.location, '32.166369, 34.810893')

    def test_create_site_none_location(self):
        self.client.sites.create('test_site')
        site = self.client.sites.get('test_site')
        self.assertEqual(site.name, 'test_site')
        self.assertIsNone(site.location)
        self.assertEqual(site.visibility, VisibilityState.TENANT)

    def test_create_site_already_exists(self):
        self._put_site()
        error_msg = "409: <Site id=`test_site` tenant=`default_tenant`> " \
                    "already exists on <Tenant name=`default_tenant`>"
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.sites.create,
                               'test_site')

    def test_create_site_invalid_location(self):
        self._test_invalid_location(self.client.sites.create)

    def test_create_site_invalid_visibility(self):
        self.assertRaisesRegex(CloudifyClientError,
                               'visibility',
                               self.client.sites.create,
                               'test_site',
                               visibility='test')

    def test_create_site_invalid_name(self):
        error_msg = "400: The `name` argument contains illegal characters."
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.sites.create,
                               'site:')

    def test_update_site(self):
        self._put_site()
        self.client.sites.update('test_site',
                                 location="50.0,50.0",
                                 visibility=VisibilityState.GLOBAL,
                                 new_name='new_site')
        site = self.client.sites.get('new_site')
        self.assertEqual(site.name, 'new_site')
        self.assertEqual(site.location, '50.0, 50.0')
        self.assertEqual(site.visibility, VisibilityState.GLOBAL)

    def test_update_site_empty_location(self):
        self._put_site()
        self.client.sites.update('test_site', location="")
        site = self.client.sites.get('test_site')
        self.assertEqual(site.name, 'test_site')
        self.assertIsNone(site.location)

    def test_update_site_same_name(self):
        self._put_site()
        self.client.sites.update('test_site', new_name='test_site')
        site = self.client.sites.get('test_site')
        self.assertEqual(site.name, 'test_site')

    def test_update_site_invalid_name(self):
        self._put_site()
        error_msg = "400: The `new_name` argument contains illegal characters."
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.sites.update,
                               'test_site',
                               new_name='site:')

        self._put_site('test_site_1')
        error_msg = "409: Invalid new name `test_site_1`, it already " \
                    "exists on <Tenant name=`default_tenant`> or with " \
                    "global visibility"
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.sites.update,
                               'test_site',
                               new_name='test_site_1')

        # Makes sure it didn't update the site
        site = self.client.sites.get('test_site')
        self.assertEqual(site.name, 'test_site')

    def test_update_site_invalid_visibility(self):
        self.assertRaisesRegex(CloudifyClientError,
                               'visibility',
                               self.client.sites.update,
                               'test_site',
                               visibility='test')

        self._put_site()
        error_msg = "400: Can't set the visibility of `test_site` to " \
                    "private because it already has wider visibility"
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.sites.update,
                               'test_site',
                               visibility=VisibilityState.PRIVATE)

    def test_update_site_invalid_location(self):
        self._test_invalid_location(self.client.sites.update)

    def test_delete_site(self):
        self._put_site()
        self.client.sites.delete('test_site')
        error_msg = "404: Requested `Site` with ID `test_site` was not found"
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.sites.get,
                               'test_site')

    def test_delete_site_not_found(self):
        error_msg = "404: Requested `Site` with ID `my_site` was not found"
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.sites.delete,
                               'my_site')

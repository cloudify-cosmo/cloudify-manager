#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

from manager_rest.test.attribute import attr
from manager_rest.test.base_test import (BaseServerTestCase,
                                         LATEST_API_VERSION)
from manager_rest.resolver_with_catalog_support import \
    (ResolverWithCatalogSupport,
     BLUEPRINT_PREFIX,
     PLUGIN_PREFIX)
from manager_rest.manager_exceptions import (InvalidPluginError,
                                             NotFoundError)


TEST_PACKAGE_NAME = 'cloudify-script-plugin'
TEST_PACKAGE_VERSION = '1.2'


@attr(client_min_version=LATEST_API_VERSION,
      client_max_version=LATEST_API_VERSION)
class TestPluginParseWithResolver(BaseServerTestCase):
    def setUp(self):
        super(TestPluginParseWithResolver, self).setUp()
        self.resolver = ResolverWithCatalogSupport()

    def test_successful_plugin_import_resolver(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION)
        self.assertIsNotNone(self.resolver.
                             fetch_import(PLUGIN_PREFIX + TEST_PACKAGE_NAME))

    def test_not_existing_plugin_import_resolver(self):
        self.assertRaises(InvalidPluginError, self.resolver.fetch_import,
                          import_url=PLUGIN_PREFIX + TEST_PACKAGE_NAME)


@attr(client_min_version=LATEST_API_VERSION,
      client_max_version=LATEST_API_VERSION)
class TestBlueprintParseWithResolver(BaseServerTestCase):
    def setUp(self):
        super(TestBlueprintParseWithResolver, self).setUp()
        self.resolver = ResolverWithCatalogSupport()
        self.blueprint_id = 'test_blueprint'
        self.import_url = BLUEPRINT_PREFIX + self.blueprint_id

    def test_successful_blueprint_import_resolver(self):
        self.put_blueprint('mock_blueprint',
                           'blueprint.yaml', self.blueprint_id)
        blueprint = self.resolver.fetch_import(self.import_url)
        self.assertIsNotNone(blueprint)

    def test_not_existing_blueprint_import_resolver(self):
        self.assertRaises(NotFoundError,
                          self.resolver.fetch_import,
                          import_url=self.import_url)

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

from manager_rest.test.base_test import BaseServerTestCase
from manager_rest.resolver_with_catalog_support import (
    ResolverWithCatalogSupport,
    BLUEPRINT_PREFIX,
    PLUGIN_PREFIX)
from manager_rest.manager_exceptions import (InvalidPluginError,
                                             NotFoundError)


TEST_PACKAGE_NAME = 'cloudify-script-plugin'
# Version 1 must be less than Version 2
TEST_PLUGIN_VERSION1 = '1.2'
TEST_PLUGIN_VERSION2 = '1.5'

PLUGIN_IMPORT_FORMAT = PLUGIN_PREFIX + "{0}?version={1}"


class TestPluginParseWithResolver(BaseServerTestCase):
    def setUp(self):
        super(TestPluginParseWithResolver, self).setUp()
        self.resolver = ResolverWithCatalogSupport()

    def test_successful_plugin_import_resolver(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PLUGIN_VERSION1)
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PLUGIN_VERSION2,
                           package_yaml='mock_blueprint/plugin2.yaml')
        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            TEST_PLUGIN_VERSION1)
        plugin_str = self.resolver.fetch_import(import_url)
        self.assertTrue('this_is_plugin_1' in plugin_str)

    def test_not_existing_plugin_import_resolver(self):
        with self.assertRaisesRegex(
                InvalidPluginError, r'Plugin .+ not found'):
            self.resolver.fetch_import(
                import_url=PLUGIN_PREFIX + TEST_PACKAGE_NAME)

    def test_fetches_max_in_range(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PLUGIN_VERSION1)
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PLUGIN_VERSION2,
                           package_yaml='mock_blueprint/plugin2.yaml')
        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            '>={0},<={1}'.format(TEST_PLUGIN_VERSION1, TEST_PLUGIN_VERSION2))
        plugin_str = self.resolver.fetch_import(import_url)
        self.assertTrue('this_is_plugin_2' in plugin_str)

        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            '>={0},<{1}'.format(TEST_PLUGIN_VERSION1, TEST_PLUGIN_VERSION2))
        plugin_str = self.resolver.fetch_import(import_url)
        self.assertTrue('this_is_plugin_1' in plugin_str)

    def test_fetches_max_in_range_with_constraint(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PLUGIN_VERSION1)
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PLUGIN_VERSION2,
                           package_yaml='mock_blueprint/plugin2.yaml')
        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            '>={0},!={1}'.format(TEST_PLUGIN_VERSION1, TEST_PLUGIN_VERSION2))
        plugin_str = self.resolver.fetch_import(import_url)
        self.assertTrue('this_is_plugin_1' in plugin_str)

    def test_no_version_found(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PLUGIN_VERSION1)
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PLUGIN_VERSION2,
                           package_yaml='mock_blueprint/plugin2.yaml')
        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            '!={0},!={1}'.format(TEST_PLUGIN_VERSION1, TEST_PLUGIN_VERSION2))
        with self.assertRaisesRegex(
                InvalidPluginError, r'No matching version was found .+'):
            self.resolver.fetch_import(import_url)
        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            '{0},{1}'.format(TEST_PLUGIN_VERSION1, TEST_PLUGIN_VERSION2))
        with self.assertRaisesRegex(
                InvalidPluginError, r'No matching version was found .+'):
            self.resolver.fetch_import(import_url)

    def test_bad_version_format(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PLUGIN_VERSION1)
        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            ',{0}'.format(TEST_PLUGIN_VERSION1))
        with self.assertRaisesRegex(
                InvalidPluginError, r'Specified version param .+ '
                                    r'are in an invalid form'):
            self.resolver.fetch_import(import_url)

    def test_fetches_max_with_general_range(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PLUGIN_VERSION1)
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PLUGIN_VERSION2,
                           package_yaml='mock_blueprint/plugin2.yaml')
        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            '')
        plugin_str = self.resolver.fetch_import(import_url)
        self.assertTrue('this_is_plugin_2' in plugin_str)


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

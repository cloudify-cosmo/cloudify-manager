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

import os
import shutil
from datetime import datetime

from manager_rest.constants import FILE_SERVER_PLUGINS_FOLDER
from manager_rest.storage import models
from manager_rest.test.base_test import BaseServerTestCase
from manager_rest.resolver_with_catalog_support import (
    ResolverWithCatalogSupport,
    BLUEPRINT_PREFIX,
    PLUGIN_PREFIX)
from manager_rest.manager_exceptions import (InvalidPluginError,
                                             NotFoundError)


TEST_PACKAGE_NAME = 'cloudify-script-plugin'
# Version 1 must be less than Version 2
TEST_PLUGIN_VERSION1 = '1.3'
TEST_PLUGIN_VERSION2 = '1.5'

PLUGIN_IMPORT_FORMAT = PLUGIN_PREFIX + "{0}?version={1}"


class TestPluginParseWithResolver(BaseServerTestCase):
    def setUp(self):
        super(TestPluginParseWithResolver, self).setUp()
        self.resolver = ResolverWithCatalogSupport(storage_manager=self.sm)
        self.plugin1 = self._plugin(
            yaml='# this_is_plugin_1',
            id='plugin1',
        )
        self.plugin2 = self._plugin(
            yaml='# this_is_plugin_2',
            id='plugin2',
            package_version=TEST_PLUGIN_VERSION2,
        )

    def _plugin_dir(self, plugin):
        return os.path.join(
            self.server_configuration.file_server_root,
            FILE_SERVER_PLUGINS_FOLDER,
            plugin.id,
        )

    def _plugin(self, yaml, **kwargs):
        plugin_kwargs = {
            'package_name': TEST_PACKAGE_NAME,
            'package_version': TEST_PLUGIN_VERSION1,
            'archive_name': 'archive.wgn',
            'uploaded_at': datetime.utcnow(),
            'wheels': [],
            'creator': self.user,
            'tenant': self.tenant,
        }
        plugin_kwargs.update(kwargs)
        plugin = models.Plugin(**plugin_kwargs)
        plugin_dir = self._plugin_dir(plugin)
        os.makedirs(plugin_dir)
        self.addCleanup(shutil.rmtree, plugin_dir)
        with open(os.path.join(plugin_dir, 'plugin.yaml'), 'w') as f:
            f.write(yaml)
        return plugin

    def test_successful_plugin_import_resolver(self):
        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            TEST_PLUGIN_VERSION1)
        plugin_str = self.resolver.fetch_import(import_url)
        assert 'this_is_plugin_1' in plugin_str

    def test_not_existing_plugin_import_resolver(self):
        with self.assertRaisesRegex(
                InvalidPluginError, r'Plugin .+ not found'):
            self.resolver.fetch_import(
                import_url=PLUGIN_PREFIX + 'other-plugin')

    def test_fetches_max_in_range(self):
        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            '>={0},<={1}'.format(TEST_PLUGIN_VERSION1, TEST_PLUGIN_VERSION2))
        plugin_str = self.resolver.fetch_import(import_url)
        assert 'this_is_plugin_2' in plugin_str

        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            '>={0},<{1}'.format(TEST_PLUGIN_VERSION1, TEST_PLUGIN_VERSION2))
        plugin_str = self.resolver.fetch_import(import_url)
        self.assertTrue('this_is_plugin_1' in plugin_str)

    def test_fetches_max_in_range_with_constraint(self):
        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            '>={0},!={1}'.format(TEST_PLUGIN_VERSION1, TEST_PLUGIN_VERSION2))
        plugin_str = self.resolver.fetch_import(import_url)
        assert 'this_is_plugin_1' in plugin_str

    def test_no_version_found(self):
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
        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            ',{0}'.format(TEST_PLUGIN_VERSION1))
        with self.assertRaisesRegex(
                InvalidPluginError, r'Specified version param .+ '
                                    r'are in an invalid form'):
            self.resolver.fetch_import(import_url)

    def test_fetches_max_with_general_range(self):
        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            '')
        plugin_str = self.resolver.fetch_import(import_url)
        assert 'this_is_plugin_2' in plugin_str

    def test_single_plugin_yaml_compatibility(self):
        import_url = PLUGIN_IMPORT_FORMAT.format(TEST_PACKAGE_NAME, '')
        plugin_str = self.resolver.fetch_import(import_url, '')
        assert plugin_str
        plugin_str = self.resolver.fetch_import(import_url, '1_3')
        assert plugin_str
        plugin_str = self.resolver.fetch_import(import_url, '1_4')
        assert plugin_str

    def test_fetches_proper_plugin_yaml(self):
        plugin1_dir = self._plugin_dir(self.plugin1)
        with open(os.path.join(plugin1_dir, 'plugin_1_3.yaml'), 'w') as f:
            f.write('# this_is_plugin_1, DSL version 1_3')

        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            TEST_PLUGIN_VERSION1,
        )
        plugin_str = self.resolver.fetch_import(import_url, '1_3')
        assert plugin_str.startswith('# this_is_plugin_1, DSL version 1_3')
        plugin_str = self.resolver.fetch_import(import_url)
        assert plugin_str.startswith('# this_is_plugin_1')
        plugin_str = self.resolver.fetch_import(import_url, '1_4')
        assert plugin_str.startswith('# this_is_plugin_1')

    def test_fetch_plugin_yaml_matching_dsl_version(self):
        plugin1_dir = self._plugin_dir(self.plugin1)
        with open(os.path.join(plugin1_dir, 'plugin_1_3.yaml'), 'w') as f:
            f.write('# this_is_plugin_1, DSL version 1_3')
        with open(os.path.join(plugin1_dir, 'plugin_1_4.yaml'), 'w') as f:
            f.write('# this_is_plugin_1, DSL version 1_4')

        import_url = PLUGIN_IMPORT_FORMAT.format(
            TEST_PACKAGE_NAME,
            TEST_PLUGIN_VERSION1,
        )
        plugin_str = self.resolver.fetch_import(import_url)
        assert plugin_str.startswith('# this_is_plugin_1')
        plugin_str = self.resolver.fetch_import(import_url, '1_3')
        assert plugin_str.startswith('# this_is_plugin_1, DSL version 1_3')
        plugin_str = self.resolver.fetch_import(import_url, '1_4')
        assert plugin_str.startswith('# this_is_plugin_1, DSL version 1_4')


class TestBlueprintParseWithResolver(BaseServerTestCase):
    def setUp(self):
        super(TestBlueprintParseWithResolver, self).setUp()
        self.resolver = ResolverWithCatalogSupport(storage_manager=self.sm)
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

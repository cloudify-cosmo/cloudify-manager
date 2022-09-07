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
from datetime import datetime

from dsl_parser import tasks, constants

from manager_rest.constants import FILE_SERVER_PLUGINS_FOLDER
from manager_rest.storage import models
from manager_rest.test.base_test import BaseServerTestCase
from manager_rest.resolver_with_catalog_support import \
    ResolverWithCatalogSupport


TEST_PACKAGE_NAME = 'cloudify-diamond-plugin'
TEST_PACKAGE_VERSION = '1.3'


class TestParseWithResolver(BaseServerTestCase):
    def setUp(self):
        super(TestParseWithResolver, self).setUp()
        self.resolver = ResolverWithCatalogSupport(storage_manager=self.sm)

    def test_successful_plugin_import_resolver(self):
        plugin = models.Plugin(
            id='plugin1',
            package_name=TEST_PACKAGE_NAME,
            package_version=TEST_PACKAGE_VERSION,
            archive_name='archive.wgn',
            uploaded_at=datetime.utcnow(),
            wheels=[],
            creator=self.user,
            tenant=self.tenant,
        )
        plugin_dir = os.path.join(
            self.server_configuration.file_server_root,
            FILE_SERVER_PLUGINS_FOLDER,
            plugin.id,
        )
        os.makedirs(plugin_dir)
        with open(os.path.join(plugin_dir, 'plugin.yaml'), 'w'):
            pass
        dsl_location = os.path.join(
            self.get_blueprint_path('mock_blueprint'),
            'blueprint_with_plugin_import.yaml')

        tasks.parse_dsl(dsl_location=dsl_location,
                        resources_base_path=self.tmpdir,
                        resolver=self.resolver)

    def test_success_with_blueprint_import_resolver(self):
        blueprint_id = 'imported_blueprint'
        self.put_blueprint('mock_blueprint',
                           'blueprint.yaml', blueprint_id)

        dsl_location = os.path.join(
            self.get_blueprint_path('mock_blueprint'),
            'blueprint_with_blueprint_import.yaml')

        plan = tasks.parse_dsl(dsl_location=dsl_location,
                               resources_base_path=self.tmpdir,
                               resolver=self.resolver)

        nodes = {node["name"] for node in plan[constants.NODES]}

        self.assertEqual(nodes, {"test", "ns--vm", "ns--http_web_server"})

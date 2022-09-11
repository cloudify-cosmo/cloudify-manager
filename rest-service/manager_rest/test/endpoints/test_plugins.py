#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import json
import mock
import os
import tarfile
import zipfile
from datetime import datetime, timedelta

from manager_rest.storage import db, models
from manager_rest.test.base_test import BaseServerTestCase

from cloudify_rest_client import exceptions
from .test_utils import generate_progress_func

TEST_PACKAGE_NAME = 'cloudify-script-plugin'
TEST_PACKAGE_VERSION = '1.3'
OLD_TEST_PACKAGE_VERSION = '1.2'


class PluginsTest(BaseServerTestCase):
    """Test plugins upload and download."""
    @classmethod
    def setUpClass(cls):
        super(PluginsTest, cls).setUpClass()
        cls.empty_plugin_path = os.path.join(cls.tmpdir, 'plugin.zip')
        with zipfile.ZipFile(cls.empty_plugin_path, 'w') as zf:
            with zf.open('plugin.wgn', 'w') as f:
                f.write(b'abcd')
            with zf.open('plugin.yaml', 'w') as f:
                f.write(b'')

    def test_get_plugin_by_id(self):
        package_name = 'test-plugin'
        package_version = '1.0.0'

        with mock.patch('wagon.show', return_value={
            'archive_name': 'plugin1',
            'package_name': package_name,
            'package_version': package_version,
        }):
            put_plugin_response = self.client.plugins.upload(
                self.empty_plugin_path)
        assert put_plugin_response.id is not None
        assert put_plugin_response.get('package_name') == package_name
        assert put_plugin_response.get('package_version') == package_version

        get_response = self.client.plugins.get(put_plugin_response.id)
        assert get_response == put_plugin_response

    def test_get_plugin_not_found(self):
        with self.assertRaises(exceptions.CloudifyClientError) as cm:
            self.client.plugins.get('DUMMY_PLUGIN_ID')
        assert cm.exception.status_code == 404

    def test_delete_plugin(self):
        plugin = models.Plugin(
            id='plug1',
            package_name=TEST_PACKAGE_NAME,
            package_version=TEST_PACKAGE_VERSION,
            archive_name=TEST_PACKAGE_NAME,
            uploaded_at=datetime.utcnow(),
            wheels=[],
            creator=self.user,
            tenant=self.tenant,
        )

        plugins_list = self.client.plugins.list()
        assert len(plugins_list) == 1
        self.client.plugins.delete(plugin.id)

        plugins_list = self.client.plugins.list()
        assert len(plugins_list) == 0

    def test_sort_list_plugins(self):
        models.Plugin(
            id='plug1',
            package_name=TEST_PACKAGE_NAME,
            package_version=OLD_TEST_PACKAGE_VERSION,
            archive_name=TEST_PACKAGE_NAME,
            uploaded_at=datetime.utcnow(),
            wheels=[],
            creator=self.user,
            tenant=self.tenant,
        )
        models.Plugin(
            id='plug2',
            package_name=TEST_PACKAGE_NAME,
            package_version=TEST_PACKAGE_VERSION,
            archive_name=TEST_PACKAGE_NAME,
            uploaded_at=datetime.utcnow() + timedelta(hours=1),
            wheels=[],
            creator=self.user,
            tenant=self.tenant,
        )

        plugins = self.client.plugins.list(sort='uploaded_at')
        assert 2 == len(plugins)
        assert OLD_TEST_PACKAGE_VERSION == plugins[0].package_version
        assert TEST_PACKAGE_VERSION == plugins[1].package_version

        plugins = self.client.plugins.list(
            sort='uploaded_at', is_descending=True)
        assert 2 == len(plugins)
        assert TEST_PACKAGE_VERSION == plugins[0].package_version
        assert OLD_TEST_PACKAGE_VERSION == plugins[1].package_version

    def test_delete_plugin_not_found(self):
        with self.assertRaises(exceptions.CloudifyClientError) as cm:
            self.client.plugins.delete('DUMMY_PLUGIN_ID')
        assert cm.exception.status_code == 404

    def test_put_same_plugin_module_twice_response_status(self):
        plugin = models.Plugin(
            id='plug1',
            package_name=TEST_PACKAGE_NAME,
            package_version=TEST_PACKAGE_VERSION,
            archive_name=TEST_PACKAGE_NAME,
            uploaded_at=datetime.utcnow(),
            wheels=[],
            creator=self.user,
            tenant=self.tenant,
        )
        with mock.patch('wagon.show', return_value={
            'archive_name': plugin.archive_name,
            'package_name': plugin.package_name,
            'package_version': plugin.package_version,
        }):
            with self.assertRaises(exceptions.CloudifyClientError) as cm:
                self.client.plugins.upload(self.empty_plugin_path)
        assert cm.exception.status_code == 409

    def test_post_plugin_package_different_versions(self):
        with mock.patch('wagon.show', return_value={
            'archive_name': 'plugin1',
            'package_name': TEST_PACKAGE_NAME,
            'package_version': TEST_PACKAGE_VERSION,
        }):
            response_a = self.client.plugins.upload(self.empty_plugin_path)
            assert response_a.id is not None

        with mock.patch('wagon.show', return_value={
            'archive_name': 'plugin2',
            'package_name': TEST_PACKAGE_NAME,
            'package_version': OLD_TEST_PACKAGE_VERSION,
        }):
            response_b = self.client.plugins.upload(self.empty_plugin_path)
            assert response_b.id is not None

        assert response_a.package_version and response_b.package_version
        assert response_a.package_version != response_b.package_version

    def test_delete_force(self):
        for source in [
            'workflow_plugins_to_install',
            'deployment_plugins_to_install',
            'host_agent_plugins_to_install',
        ]:
            plugin = models.Plugin(
                id='plug1',
                package_name=TEST_PACKAGE_NAME,
                package_version=TEST_PACKAGE_VERSION,
                archive_name=TEST_PACKAGE_NAME,
                uploaded_at=datetime.utcnow(),
                wheels=[],
                creator=self.user,
                tenant=self.tenant,
            )
            blueprint_plan = {
                'workflow_plugins_to_install': [],
                'deployment_plugins_to_install': [],
                'host_agent_plugins_to_install': [],
            }
            blueprint_plan[source].append({
                'package_name': plugin.package_name,
                'package_version': plugin.package_version,
            })
            bp = models.Blueprint(
                id='bp1',
                plan=blueprint_plan,
                state='uploaded',
                creator=self.user,
                tenant=self.tenant,
            )

            with self.assertRaises(exceptions.PluginInUseError):
                self.client.plugins.delete(plugin.id)
            assert len(self.client.plugins.list()) == 1
            self.client.plugins.delete(plugin_id=plugin.id, force=True)
            assert len(self.client.plugins.list()) == 0

            db.session.delete(bp)
            db.session.commit()

    def test_plugin_upload_progress(self):
        large_plugin_path = os.path.join(self.tmpdir, 'large_plugin.zip')
        with open(large_plugin_path, 'w') as f:
            for _ in range(10000):
                f.write('abcd')

        total_size = os.path.getsize(large_plugin_path)

        with mock.patch('wagon.show', return_value={
            'archive_name': 'plugin1',
            'package_name': TEST_PACKAGE_NAME,
            'package_version': TEST_PACKAGE_VERSION,
            'wheels': [],
            'build_server_os_properties': {},
        }):
            # asserts are in the progress callback
            self.client.plugins.upload(
                large_plugin_path,
                progress_callback=generate_progress_func(
                    total_size=total_size),
            )

    def test_plugin_upload_without_yaml(self):
        plugin_without_yaml = os.path.join(self.tmpdir, 'no-yaml.whl')
        with open(plugin_without_yaml, 'w') as f:
            f.write('abcd')

        with mock.patch('wagon.show', return_value={
            'archive_name': 'plugin1',
            'package_name': TEST_PACKAGE_NAME,
            'package_version': TEST_PACKAGE_VERSION,
            'wheels': [],
            'build_server_os_properties': {},
        }):
            plugin = self.client.plugins.upload(plugin_without_yaml)
        assert plugin.id is not None

    def test_plugin_download_progress(self):
        large_plugin_path = os.path.join(self.tmpdir, 'large_plugin.whl')
        with open(large_plugin_path, 'w') as f:
            for _ in range(10000):
                f.write('abcd')

        with mock.patch('wagon.show', return_value={
            'archive_name': 'plugin1',
            'package_name': TEST_PACKAGE_NAME,
            'package_version': TEST_PACKAGE_VERSION,
        }):
            plugin = self.client.plugins.upload(large_plugin_path)

        total_size = os.path.getsize(large_plugin_path)
        # asserts are in the progress callback
        self.client.plugins.download(
            plugin.id,
            os.path.join(self.tmpdir, 'downloaded-plugin.whl'),
            generate_progress_func(total_size=total_size),
        )

    def test_caravan_upload(self):
        caravan_path = os.path.join(self.tmpdir, 'caravan.cvn')
        caravan_dir = os.path.join(self.tmpdir, 'created-caravan')
        with tarfile.open(caravan_path, 'w:gz') as tf:
            os.makedirs(os.path.join(caravan_dir, 'plugin1'))
            os.makedirs(os.path.join(caravan_dir, 'plugin2'))
            for filename in [
                os.path.join(caravan_dir, 'plugin1', 'plugin1.wgn'),
                os.path.join(caravan_dir, 'plugin1', 'plugin1.yaml'),
                os.path.join(caravan_dir, 'plugin2', 'plugin2.wgn'),
                os.path.join(caravan_dir, 'plugin2', 'plugin2.yaml'),
            ]:
                with open(filename, 'w') as f:
                    pass
            with open(os.path.join(caravan_dir, 'METADATA'), 'w') as f:
                json.dump({
                    'plugin1/plugin1.wgn': 'plugin1/plugin1.yaml',
                    'plugin2/plugin2.wgn': 'plugin2/plugin2.yaml',
                }, f)
            tf.add(caravan_dir, arcname='caravan')

        plugin1_desc = {
            'archive_name': 'plugin1',
            'package_name': 'package1',
            'package_version': '1.0.0',
        }
        plugin2_desc = {
            'archive_name': 'plugin2',
            'package_name': 'package2',
            'package_version': '1.0.0',
        }
        with mock.patch('wagon.show', side_effect=[
            plugin1_desc,
            plugin1_desc,
            plugin2_desc,
            plugin2_desc,
        ]):
            response = self.client.plugins.upload(caravan_path)
        assert len(response) == 2
        plugins_list = self.client.plugins.list()
        assert len(plugins_list) == 2

    def test_plugin_upload_with_title(self):
        with mock.patch('wagon.show', return_value={
            'archive_name': 'plugin1',
            'package_name': TEST_PACKAGE_NAME,
            'package_version': TEST_PACKAGE_VERSION,
        }):
            uploaded_plugin = self.client.plugins.upload(
                self.empty_plugin_path,
                plugin_title='test')
        get_plugin_by_id_response = self.client.plugins.get(uploaded_plugin.id)
        assert get_plugin_by_id_response.title == 'test'

    def test_plugin_upload_check_default_title(self):
        with mock.patch('wagon.show', return_value={
            'archive_name': 'plugin1',
            'package_name': TEST_PACKAGE_NAME,
            'package_version': TEST_PACKAGE_VERSION,
        }):
            uploaded_plugin = self.client.plugins.upload(
                self.empty_plugin_path)
        assert uploaded_plugin.get('title') == TEST_PACKAGE_NAME
        get_plugin_by_id_response = self.client.plugins.get(uploaded_plugin.id)
        assert get_plugin_by_id_response.title == TEST_PACKAGE_NAME

    def test_plugin_upload_blueprint_labels(self):
        plugin_with_labels = os.path.join(self.tmpdir, 'plugin.zip')
        with zipfile.ZipFile(plugin_with_labels, 'w') as zf:
            with zf.open('plugin.wgn', 'w') as f:
                f.write(b'abcd')
            with zf.open('plugin.yaml', 'w') as f:
                f.write(b'''
---
plugins:
  plug1:
    package_name: package1

blueprint_labels:
  csys-obj-type:
    values:
      - aws
  arch:
    values:
      - docker
      - k8s
labels:
  csys-obj-type:
    values:
      - eks
  arch:
    values:
      - k8s
resource_tags:
  key1: value1
  key2: value2
''')
        with mock.patch('wagon.show', side_effect=[
            ValueError(''),  # error first, it's a zipfile, not a wagon
            {
                'archive_name': 'plugin1',
                'package_name': TEST_PACKAGE_NAME,
                'package_version': TEST_PACKAGE_VERSION,
            }
        ]):
            uploaded_plugin = self.client.plugins.upload(plugin_with_labels)
        plugin_id = uploaded_plugin.get('id')
        plugin = self.client.plugins.get(plugin_id)
        assert plugin.blueprint_labels == {
            'arch': ['docker', 'k8s'],
            'csys-obj-type': ['aws'],
        }
        assert plugin.labels == {
            'arch': ['k8s'],
            'csys-obj-type': ['eks'],
        }
        assert plugin.resource_tags == {
            'key1': 'value1',
            'key2': 'value2',
        }

    def test_plugin_upload_blueprint_invalid_labels(self):
        plugin_with_labels = os.path.join(self.tmpdir, 'plugin.zip')
        with zipfile.ZipFile(plugin_with_labels, 'w') as zf:
            with zf.open('plugin.wgn', 'w') as f:
                f.write(b'abcd')
            with zf.open('plugin.yaml', 'w') as f:
                f.write(b'''
blueprint_labels:
  csys-obj-type:
    values:
      invalid value
  arch:
    not valid YAML file
''')
        with mock.patch('wagon.show', side_effect=[
            ValueError(''),  # error first, it's a zipfile, not a wagon
            {
                'archive_name': 'plugin1',
                'package_name': TEST_PACKAGE_NAME,
                'package_version': TEST_PACKAGE_VERSION,
            }
        ]):
            with self.assertRaises(exceptions.CloudifyClientError) as cm:
                self.client.plugins.upload(plugin_with_labels)
        assert cm.exception.status_code == 400

########
# Copyright (c) 2020 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import pytest
import requests

from cloudify.models_states import BlueprintUploadState
from cloudify.utils import ipv6_url_compat
from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.framework import docker
from integration_tests.tests.utils import get_resource as resource

from packaging.version import parse as parse_version

pytestmark = pytest.mark.group_deployments


class BlueprintUploadAutouploadPluginsTest(AgentlessTestCase):

    def test_blueprint_upload_autoupload_plugins(self):
        self._upload_and_verify_blueprint(
            'bp',
            'blueprint_with_plugins_from_catalog.yaml')

        plugins = {p.package_name: p.package_version
                   for p in self.client.plugins.list()}
        self.assertEqual(plugins["cloudify-openstack-plugin"], "3.2.16")
        self.assertIn("cloudify-utilities-plugin", plugins)
        self.assertGreater(parse_version(plugins["cloudify-fabric-plugin"]),
                           parse_version("2"))

    def test_blueprint_upload_autoupload_plugins_bad_version(self):
        blueprint_id = 'bp_bad_version'
        blueprint_filename = 'blueprint_with_plugins_from_' \
                             'catalog_bad_version.yaml'
        self.assertRaisesRegexp(
            CloudifyClientError,
            'Couldn\'t find plugin "cloudify-openstack-plugin" with.*=3.1.99',
            self.client.blueprints.upload,
            resource('dsl/{}'.format(blueprint_filename)),
            entity_id=blueprint_id)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint['state'], BlueprintUploadState.INVALID)

    def test_blueprint_upload_autoupload_plugins_bad_plugin(self):
        blueprint_id = 'bp_bad_plugin'
        blueprint_filename = 'blueprint_with_plugins_from_' \
                             'catalog_bad_plugin.yaml'
        self.assertRaisesRegexp(
            CloudifyClientError,
            'Couldn\'t find plugin "my-custom-plugin"',
            self.client.blueprints.upload,
            resource('dsl/{}'.format(blueprint_filename)),
            entity_id=blueprint_id)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint['state'], BlueprintUploadState.INVALID)

    def test_blueprint_upload_autoupload_plugins_conflicting_versions(self):
        blueprint_id = 'bp_two_plugin_versions'
        blueprint_filename = 'blueprint_with_plugins_from_' \
                             'catalog_conflicting_versions.yaml'
        self.assertRaisesRegexp(
            CloudifyClientError,
            'Could not merge \'plugins\' due to conflict on \'openstack\'',
            self.client.blueprints.upload,
            resource('dsl/{}'.format(blueprint_filename)),
            entity_id=blueprint_id)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint['state'], BlueprintUploadState.INVALID)

    def test_blueprint_upload_autoupload_plugins_newer_version(self):
        self._upload_and_verify_blueprint(
            'bp1_os2',
            'blueprint_with_plugins_from_catalog_os2.yaml')

        plugin_versions = sorted(p.package_version
                                 for p in self.client.plugins.list())
        self.assertEqual(len(plugin_versions), 1)
        self.assertRegex(plugin_versions[0], "2.*")

        self._upload_and_verify_blueprint(
            'bp1_os3',
            'blueprint_with_plugins_from_catalog_os3.yaml')

        plugin_versions = sorted(p.package_version for
                                 p in self.client.plugins.list())
        self.assertEqual(len(plugin_versions), 2)
        self.assertRegex(plugin_versions[0], "2.*")
        self.assertGreater(parse_version(plugin_versions[1]),
                           parse_version("3"))

    def test_blueprint_upload_autoupload_plugins_older_version(self):
        self._upload_and_verify_blueprint(
            'bp1_os3',
            'blueprint_with_plugins_from_catalog_os3.yaml')

        plugin_versions = sorted(p.package_version
                                 for p in self.client.plugins.list())
        self.assertEqual(len(plugin_versions), 1)
        self.assertGreater(parse_version(plugin_versions[0]),
                           parse_version("3"))

        self._upload_and_verify_blueprint(
            'bp1_os2',
            'blueprint_with_plugins_from_catalog_os2.yaml')

        plugin_versions = sorted(p.package_version
                                 for p in self.client.plugins.list())
        self.assertEqual(len(plugin_versions), 2)
        self.assertRegex(plugin_versions[0], "2.*")
        self.assertGreater(parse_version(plugin_versions[1]),
                           parse_version("3"))

    def test_blueprint_upload_autoupload_plugins_network_error(self):
        # block github in /etc/hosts
        docker.execute(
            self.env.container_id,
            'sh -c "sudo cat /etc/hosts > /tmp/old_hosts"')
        docker.execute(
            self.env.container_id,
            'sh -c "echo 127.0.0.1  github.com > /tmp/new_hosts"')
        docker.execute(
            self.env.container_id,
            'sh -c "cat /tmp/new_hosts > /etc/hosts"')

        blueprint_id = 'bp_os3_no_github'
        blueprint_filename = 'blueprint_with_plugins_from_catalog_os3.yaml'
        self.assertRaisesRegexp(
            CloudifyClientError,
            'Couldn\'t download plugin from',
            self.client.blueprints.upload,
            resource('dsl/{}'.format(blueprint_filename)),
            entity_id=blueprint_id)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint['state'], BlueprintUploadState.INVALID)

        docker.execute(
            self.env.container_id,
            'sh -c "cat /tmp/old_hosts > /etc/hosts"')

    def _upload_and_verify_blueprint(self, blueprint_id, blueprint_filename):
        blueprint = self.client.blueprints.upload(
            resource('dsl/{}'.format(blueprint_filename)),
            entity_id=blueprint_id)
        self.assertEqual(blueprint['state'], BlueprintUploadState.UPLOADED)

    def _verify_blueprint_uploaded(self, blueprint, blueprint_filename):
        self.assertEqual(blueprint.state, BlueprintUploadState.UPLOADED)
        self.assertEqual(blueprint.main_file_name, blueprint_filename)
        self.assertNotEqual(blueprint.plan, None)
        self._verify_blueprint_files(blueprint.id, blueprint_filename)

    def _verify_blueprint_files(self, blueprint_id, blueprint_filename):
        # blueprint available in manager resources
        admin_headers = self.client._client.headers
        resp = requests.get(
            'https://{0}:53333/resources/blueprints/default_tenant/'
            '{1}/{2}'.format(ipv6_url_compat(self.get_manager_ip()),
                             blueprint_id,
                             blueprint_filename),
            headers=admin_headers,
            verify=False
        )
        self.assertEqual(resp.status_code, requests.status_codes.codes.ok)
        # blueprint archive available in uploaded blueprints
        resp = requests.get(
            'https://{0}:53333/uploaded-blueprints/default_tenant/'
            '{1}/{1}.tar.gz'.format(
                ipv6_url_compat(self.get_manager_ip()),
                blueprint_id),
            headers=admin_headers,
            verify=False
        )
        self.assertEqual(resp.status_code, requests.status_codes.codes.ok)

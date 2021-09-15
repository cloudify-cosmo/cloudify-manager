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

    def _upload_and_verify_blueprint(self, blueprint_id, blueprint_filename):
        blueprint = self.client.blueprints.upload(
            resource('dsl/{}'.format(blueprint_filename)),
            entity_id=blueprint_id)
        self.assertEqual(blueprint['state'], BlueprintUploadState.UPLOADED)
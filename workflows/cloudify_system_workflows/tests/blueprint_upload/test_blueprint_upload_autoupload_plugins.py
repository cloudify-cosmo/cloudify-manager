import os
import mock
import yaml
import json
import pytest
import unittest
import tempfile

from cloudify import utils as cloudify_utils
from cloudify_system_workflows.blueprint import upload, extract_parser_context
from cloudify_system_workflows.dsl_import_resolver\
    .resolver_with_catalog_support import PLUGIN_CATALOG_URL
from cloudify.exceptions import InvalidBlueprintImport

from dsl_parser import constants, tasks
from dsl_parser import utils as dsl_parser_utils
from dsl_parser.exceptions import DSLParsingException


mock_plugins_catalog = [
    {
        "description": "A Cloudify Plugin that provisions resources in OpenStack using the OpenStack SDK. Note, this plugin is not compatible with the OpenStack plugin.",
        "icon": "https://cloudify.co/wp-content/uploads/2019/08/oslogo.png",
        "name": "cloudify-openstack-plugin",
        "releases": "https://github.com/cloudify-cosmo/cloudify-openstack-plugin/releases",
        "title": "OpenStack",
        "versions": {   
            "2.14.17": {
                "wagons": [
                    {
                        "name": "Centos Core",
                        "url": "cloudify-openstack-plugin_2.14.17.wgn"
                    },
                ],
                "yaml": "cloudify-openstack-plugin/2.14.17/plugin.yaml"
            },
            "3.2.21": {
                "wagons": [
                    {
                        "name": "Centos Core",
                        "url": "cloudify-openstack-plugin_3.2.21.wgn"
                    },
                ],
                "yaml": "cloudify-openstack-plugin/3.2.21/plugin.yaml"
            },
            "3.2.22": {
                "wagons": [
                    {
                        "name": "Redhat Maipo",
                        "url": "cloudify-openstack-plugin_3.2.22.wgn"
                    },
                ],
                "yaml": "cloudify-openstack-plugin/3.2.22/plugin.yaml"
            },
        }
    },
]
plugins_versions = {}


@pytest.fixture
def mock_client():
    client = mock.Mock()
    client.plugins.list = lambda package_name: \
        plugins_versions.get(package_name, [])
    client.manager.get_managers = lambda: [{
        'version': '6.4.0',
        'edition': 'premium',
        'distribution': 'Centos',
        'distro_release': 'core',
    }]
    with mock.patch(
        'cloudify_system_workflows.dsl_import_resolver'
        '.resolver_with_catalog_support.ResolverWithCatalogSupport'
        '._download_file',
        side_effect=local_download_file):
        yield client

def local_download_file(url, dest_path, target_filename=None):
    if url == PLUGIN_CATALOG_URL:
        target_filename = 'plugin_catalog.json'
        file_path = os.path.join(dest_path, target_filename)
        json.dump(mock_plugins_catalog, open(file_path, "w"))
        return file_path
    elif url.endswith('.wgn'):
        p_name, p_version = url.strip('.wgn').split('_')
        plugin = mock.MagicMock()
        plugin.package_name = p_name
        plugin.package_version = p_version
        plugins_versions.setdefault(p_name, []).append(plugin)
        return


class TestPluginAutoupload:
    file_server_root = os.path.join(
        os.path.dirname(__file__),
        '..', '..', '..', '..', 'resources', 'rest-service')

    def _parse_plugin_import(
            self, mock_client, import_url, clear_plugins=True):
        if clear_plugins:
            plugins_versions.clear()
        parser_context = extract_parser_context(
            None,
            resolver_parameters={'file_server_root': self.file_server_root,
                                 'client': mock_client})
        import_resolver = parser_context['resolver']
        plugin = import_resolver.retrieve_plugin(import_url)
        return plugin

    def test_autoupload_plugins(self, mock_client):
        plugin = self._parse_plugin_import(
            mock_client,
            'plugin:cloudify-openstack-plugin?version= <=2.14.24')
        assert plugin.package_name == 'cloudify-openstack-plugin'
        assert plugin.package_version == '2.14.17'

    def test_autoupload_plugins_picks_max_for_distro(self, mock_client):
        plugin = self._parse_plugin_import(
            mock_client,
            'plugin:cloudify-openstack-plugin')
        assert plugin.package_name == 'cloudify-openstack-plugin'
        assert plugin.package_version == '3.2.21'

    def test_autoupload_plugins_bad_version(self, mock_client):
        with pytest.raises(
                InvalidBlueprintImport,
                match=r'Couldn\'t find plugin.* with version >=4.0.0'):
            plugin = self._parse_plugin_import(
                mock_client,
                'plugin:cloudify-openstack-plugin?version= >=4.0.0')

    def test_autoupload_plugins_bad_plugin(self, mock_client):
        with pytest.raises(
                InvalidBlueprintImport,
                match=r'Couldn\'t find plugin "my-custom-plugin\"'):
            plugin = self._parse_plugin_import(
                mock_client,
                'plugin:my-custom-plugin')

    def test_autoupload_plugins_old_after_new(self, mock_client):
        plugin = self._parse_plugin_import(
            mock_client,
            'plugin:cloudify-openstack-plugin')
        assert plugin.package_name == 'cloudify-openstack-plugin'
        assert plugin.package_version == '3.2.21'
        plugin = self._parse_plugin_import(
            mock_client,
            'plugin:cloudify-openstack-plugin?version= <3',
            clear_plugins=False)
        # more strict requirement -> older plugin is downloaded
        assert plugin.package_name == 'cloudify-openstack-plugin'
        assert plugin.package_version == '2.14.17'

    def test_autoupload_plugins_new_after_old(self, mock_client):
        plugin = self._parse_plugin_import(
            mock_client,
            'plugin:cloudify-openstack-plugin?version= <3')
        assert plugin.package_name == 'cloudify-openstack-plugin'
        assert plugin.package_version == '2.14.17'
        plugin = self._parse_plugin_import(
            mock_client,
            'plugin:cloudify-openstack-plugin',
            clear_plugins=False)
        # requirement already satisfied -> newer plugin not downloaded
        assert plugin.package_name == 'cloudify-openstack-plugin'
        assert plugin.package_version == '2.14.17'

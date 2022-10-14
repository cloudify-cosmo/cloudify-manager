import os
import mock
import pytest

from cloudify_system_workflows.blueprint import extract_parser_context
from cloudify.exceptions import InvalidBlueprintImport

MARKETPLACE_API_UPL = "http://127.0.0.1"

mock_plugin_data = {
    "items": [
        {
            "name": "cloudify-openstack-plugin",
            "logo_url":
                "https://cloudify.co/wp-content/uploads/2019/08/oslogo.png",
            "id": "6f58d23f-f5e5-4477-8dff-7684bba8e7bf"
        },
    ]
}
mock_plugin_data_empty = {
    "items": []
}


mock_plugin_versions = {
    "items": [
        {
            "version": "2.14.17",
            "yaml_urls": [{
                "dsl_version": "cloudify_dsl_1_3",
                "url": "cloudify-openstack-plugin/2.14.17/plugin.yaml"
            }],
            "wagon_urls": [{
                "release": "Centos Core",
                "url": "cloudify-openstack-plugin_2.14.17.wgn"
            }]
        },
        {
            "version": "3.2.21",
            "yaml_urls": [
                {
                    "dsl_version": "cloudify_dsl_1_3",
                    "url": "cloudify-openstack-plugin/3.2.21/plugin.yaml",
                },
                {
                    "dsl_version": "cloudify_dsl_1_4",
                    "url": "cloudify-openstack-plugin/3.2.21/v2_plugin.yaml",
                }
            ],
            "wagon_urls": [{
                "release": "Centos Core",
                "url": "cloudify-openstack-plugin_3.2.21.wgn"
            }]
        },
        {
            "version": "3.2.22",
            "yaml_urls": [{
                "dsl_version": "cloudify_dsl_1_4",
                "url": "cloudify-openstack-plugin/3.2.22/v2_plugin.yaml",
            }],
            "wagon_urls": [{
                "release": "Redhat Maipo",
                "url": "cloudify-openstack-plugin_3.2.22.wgn"
            }]
        },
    ]
}

plugins_versions = {}
plugin_yamls = []


def mock_requests_get(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code
            self.ok = (self.status_code == 200)

        def json(self):
            return self.json_data

    if args[0].startswith(MARKETPLACE_API_UPL + "/plugins?name"):
        plugin_name = args[0].split('?name=')[-1]
        if plugin_name == 'cloudify-openstack-plugin':
            return MockResponse(mock_plugin_data, 200)
        return MockResponse(mock_plugin_data_empty, 200)
    if args[0].startswith(MARKETPLACE_API_UPL + "/plugins") and \
            args[0].endswith("/versions"):
        return MockResponse(mock_plugin_versions, 200)

    return MockResponse(None, 404)


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
    with mock.patch('cloudify_system_workflows.dsl_import_resolver'
                    '.resolver_with_catalog_support.ResolverWithCatalogSupport'
                    '._download_file', side_effect=local_download_file):
        yield client


def local_download_file(url, dest_path, target_filename=None):
    if url.endswith('.wgn'):
        p_name, p_version = url.strip('.wgn').split('_')
        plugin = mock.MagicMock()
        plugin.package_name = p_name
        plugin.package_version = p_version
        plugins_versions.setdefault(p_name, []).append(plugin)
        return
    if url.endswith('.yaml'):
        plugin_yamls.append(url.split('/')[-1])


class TestPluginAutoupload:
    file_server_root = os.path.join(
        os.path.dirname(__file__),
        '..', '..', '..', '..', 'resources', 'rest-service')

    @mock.patch('requests.get', side_effect=mock_requests_get)
    def _parse_plugin_import(
            self, mock_client, import_url, mock_requests, clear_plugins=True,
            dsl_version=None):
        plugin_yamls.clear()
        if clear_plugins:
            plugins_versions.clear()
        parser_context = extract_parser_context(
            None,
            resolver_parameters={'file_server_root': self.file_server_root,
                                 'marketplace_api_url': MARKETPLACE_API_UPL,
                                 'client': mock_client})
        import_resolver = parser_context['resolver']
        plugin = import_resolver.retrieve_plugin(import_url, dsl_version)
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

    def test_autoupload_plugins_picks_correct_dsl_yaml(self, mock_client):
        plugin = self._parse_plugin_import(
            mock_client,
            'plugin:cloudify-openstack-plugin', dsl_version='1_3')
        assert plugin.package_name == 'cloudify-openstack-plugin'
        assert plugin.package_version == '3.2.21'
        assert plugin_yamls == ['plugin.yaml']

        plugin = self._parse_plugin_import(
            mock_client,
            'plugin:cloudify-openstack-plugin', dsl_version='1_4')
        assert plugin.package_name == 'cloudify-openstack-plugin'
        assert plugin.package_version == '3.2.21'
        assert plugin_yamls == ['v2_plugin.yaml']

    def test_autoupload_plugins_bad_version(self, mock_client):
        with pytest.raises(
                InvalidBlueprintImport,
                match=r'Couldn\'t find plugin.* with version >=4.0.0'):
            self._parse_plugin_import(
                mock_client,
                'plugin:cloudify-openstack-plugin?version= >=4.0.0')

    def test_autoupload_plugins_bad_plugin(self, mock_client):
        with pytest.raises(
                InvalidBlueprintImport,
                match=r'Couldn\'t find plugin "my-custom-plugin\"'):
            self._parse_plugin_import(
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

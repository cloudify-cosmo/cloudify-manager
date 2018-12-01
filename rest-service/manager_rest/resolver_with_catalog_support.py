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
import glob
from urlparse import parse_qs
from distutils.version import LooseVersion

from dsl_parser import parser
from dsl_parser.import_resolver.default_import_resolver import (
    DefaultImportResolver)

from manager_rest import config
from manager_rest.storage import get_storage_manager
from manager_rest.constants import (
    FILE_SERVER_PLUGINS_FOLDER,
    FILE_SERVER_BLUEPRINTS_FOLDER)
from manager_rest.manager_exceptions import InvalidPluginError
from manager_rest.storage.models import (Plugin,
                                         Blueprint)

PLUGIN_PREFIX = 'plugin:'
BLUEPRINT_PREFIX = 'blueprint:'


class ResolverWithCatalogSupport(DefaultImportResolver):
    """A resolver which translates plugin-catalog style urls to file:// urls.

    For example:
    The URL: `plugin:cloudify-openstack-plugin/2.0.1` will be
    translated to: `file:///opt/manager/resources/<PLUGINS_FOLDER>/<id>`,
    where <id> is the id of the plugin looked up for the current tenant.
    The version is optional.

    The URL: `blueprint:hello_world` will be translated to:
    `file:///opt/manager/resources/<BLUEPRINTS_FOLDER>/<tenant>/<id>`,
    where <id> is the id of the blueprint looked up for the current tenant.
    """
    @staticmethod
    def _is_plugin_url(import_url):
        return import_url.startswith(PLUGIN_PREFIX)

    @staticmethod
    def _is_blueprint_url(import_url):
        return import_url.startswith(BLUEPRINT_PREFIX)

    def fetch_import(self, import_url):
        if self._is_blueprint_url(import_url):
            return self._fetch_blueprint_import(import_url)
        elif self._is_plugin_url(import_url):
            return self._fetch_plugin_import(import_url)
        return super(ResolverWithCatalogSupport, self).fetch_import(import_url)

    def _fetch_plugin_import(self, import_url):
        import_url = self._resolve_plugin_yaml_url(import_url)
        return super(ResolverWithCatalogSupport, self).fetch_import(import_url)

    @staticmethod
    def _make_plugin_filters(plugin_spec):
        """Parse the plugin spec to a dict of filters for the sql query

        >>> _make_plugin_filters('cloudify-openstack-plugin')
        {'package_name': 'cloudify-openstack-plugin'}
        >>> _make_plugin_filters('cool?version=1.0.2')
        {'package_name': 'cool', 'package_version': '1.0.2'}
        >>> _make_plugin_filters('cool?version=1.0.2&distribution=centos')
        {'package_name': 'cool', 'package_version': '1.0.2',
         'distribution': 'centos'}
        """
        filter_renames = {'version': 'package_version',
                          'distribution': 'distribution'}
        name, _, params = plugin_spec.partition('?')
        filters = {}
        for filter_name, value in parse_qs(params).items():
            renamed = filter_renames.get(filter_name)
            if renamed is None:
                raise InvalidPluginError(
                    'Error parsing spec for plugin {0}: invalid parameter {1}'
                    .format(name, filter_name))
            filters[renamed] = value
        return name, filters

    def _resolve_plugin_yaml_url(self, import_url):
        plugin_spec = import_url.replace(PLUGIN_PREFIX, '', 1).strip()
        name, plugin_filters = self._make_plugin_filters(plugin_spec)
        plugin = self._find_plugin(name, plugin_filters)
        return self._make_plugin_yaml_url(plugin)

    @staticmethod
    def _find_plugin(name, filters):
        filters['package_name'] = name
        sm = get_storage_manager()
        plugins = sm.list(Plugin, filters=filters)
        if not plugins:
            version_message = ' (query: {0})'.format(filters) \
                if filters else ''
            raise InvalidPluginError(
                'Plugin {0}{1} not found'.format(name, version_message))
        return max(plugins,
                   key=lambda plugin: LooseVersion(plugin.package_version))

    @staticmethod
    def _make_plugin_yaml_url(plugin):
        plugin_path = os.path.join(
            config.instance.file_server_root,
            FILE_SERVER_PLUGINS_FOLDER,
            plugin.id)
        yaml_files = glob.glob(os.path.join(plugin_path, '*.yaml'))
        if len(yaml_files) != 1:
            raise InvalidPluginError(
                'Plugin {0}: expected one yaml file, but found {1}'
                .format(plugin.package_name, len(yaml_files)))
        filename = os.path.join(plugin_path, yaml_files[0])
        return 'file://{0}'.format(filename)

    def _resolve_blueprint_url(self, import_url):
        main_blueprint = import_url.replace(BLUEPRINT_PREFIX, '', 1).strip()
        blueprint = self._get_blueprint(main_blueprint)
        return self._make_blueprint_url(blueprint)

    def _fetch_blueprint_import(self, import_url):
        """
        :param import_url: blueprint id in the catalog.
        :return: Blueprint of type Holder with all imports already resolved.
        """
        import_url = self._resolve_blueprint_url(import_url)
        main_blueprint = super(ResolverWithCatalogSupport, self).\
            fetch_import(import_url)
        _, merged_blueprint = parser.resolve_blueprint_imports(
            dsl_string=main_blueprint,
            dsl_location=import_url,
            resources_base_path=config.instance.file_server_root,
            resolver=self,
            validate_version=False)
        return merged_blueprint

    @staticmethod
    def _get_blueprint(name):
        return get_storage_manager().get(Blueprint, name)

    @staticmethod
    def _make_blueprint_url(blueprint):
        blueprint_path = os.path.join(
            config.instance.file_server_root,
            FILE_SERVER_BLUEPRINTS_FOLDER,
            blueprint.tenant_name,
            blueprint.id)
        filename = os.path.join(blueprint_path, blueprint.main_file_name)
        return 'file://{0}'.format(filename)

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
from flask import current_app
from distutils.version import LooseVersion

from dsl_parser import constants
from dsl_parser import utils as dsl_parser_utils
from dsl_parser.import_resolver.default_import_resolver import (
    DefaultImportResolver
)

from manager_rest import config
from manager_rest.storage import get_storage_manager
from manager_rest.constants import (
    PROVIDER_CONTEXT_ID,
    FILE_SERVER_PLUGINS_FOLDER
)
from manager_rest.manager_exceptions import InvalidPluginError
from manager_rest.storage.models import ProviderContext, Plugin


def get_parser_context(sm=None):
    sm = sm or get_storage_manager()
    if not hasattr(current_app, 'parser_context'):
        update_parser_context(sm.get(
            ProviderContext,
            PROVIDER_CONTEXT_ID
        ).context)
    return current_app.parser_context


def update_parser_context(context):
    current_app.parser_context = _extract_parser_context(context)


def _extract_parser_context(context):
    context = context or {}
    cloudify_section = context.get(constants.CLOUDIFY, {})
    resolver_section = cloudify_section.get(
        constants.IMPORT_RESOLVER_KEY) or {}
    resolver_section.setdefault('implementation',
                                'manager_rest.app_context:ResolverWithPlugins')
    resolver = dsl_parser_utils.create_import_resolver(resolver_section)
    return {
        'resolver': resolver,
        'validate_version': cloudify_section.get(
            constants.VALIDATE_DEFINITIONS_VERSION, True)
    }


class ResolverWithPlugins(DefaultImportResolver):
    """A resolver which translates plugin-style urls to file:// urls.

    The URL: `plugin:cloudify-openstack-plugin/2.0.1` will be
    translated to: `file:///opt/manager/resources/plugins/<id>`, where <id>
    is the id of the plugin looked up for the current tenant.

    The version is optional
    """
    PREFIX = 'plugin:'

    def fetch_import(self, import_url):
        if self._is_plugin_url(import_url):
            import_url = self._resolve_plugin_yaml_url(import_url)
        return super(ResolverWithPlugins, self).fetch_import(import_url)

    def _is_plugin_url(self, import_url):
        return import_url.startswith(self.PREFIX)

    def _resolve_plugin_yaml_url(self, import_url):
        parts = import_url.replace(self.PREFIX, '', 1).strip().split('/')
        name = parts[0]
        version = parts[1] if len(parts) > 1 else None
        plugin = self._find_plugin(name, version)
        return self._make_plugin_yaml_url(plugin)

    def _find_plugin(self, name, version=None):
        filters = {'package_name': name}
        if version is not None:
            filters['package_version'] = version
        sm = get_storage_manager()
        plugins = sm.list(Plugin, filters=filters)
        if not plugins:
            version_message = ' (version: {0})'.format(version) \
                if version is not None else ''
            raise InvalidPluginError(
                'Plugin {0}{1} not found'.format(name, version_message))
        return max(plugins,
                   key=lambda plugin: LooseVersion(plugin.package_version))

    def _make_plugin_yaml_url(self, plugin):
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

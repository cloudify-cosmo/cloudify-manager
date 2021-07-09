#########
# Copyright (c) 2020 Cloudify Platform Ltd. All rights reserved
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

import collections
import difflib
import os
import shutil
import typing
from datetime import datetime, timezone
from functools import lru_cache
from os import chmod, environ, stat
from os.path import exists, isfile, join
from shutil import move
from tempfile import TemporaryDirectory, mktemp

import click
import yaml

from cloudify._compat import parse_qs, parse_version

from dsl_parser.constants import (CLOUDIFY,
                                  IMPORT_RESOLVER_KEY,
                                  WORKFLOW_PLUGINS_TO_INSTALL,
                                  DEPLOYMENT_PLUGINS_TO_INSTALL,
                                  HOST_AGENT_PLUGINS_TO_INSTALL,
                                  PLUGIN_PACKAGE_NAME,
                                  PLUGIN_PACKAGE_VERSION)
from dsl_parser.models import Plan
from dsl_parser import exceptions as dsl_parser_exceptions
from dsl_parser import utils as dsl_parser_utils

from manager_rest.constants import (FILE_SERVER_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                                    PROVIDER_CONTEXT_ID,
                                    SUPPORTED_ARCHIVE_TYPES)
from manager_rest.flask_utils import (setup_flask_app, set_admin_current_user,
                                      get_tenant_by_name, set_tenant_in_app)
from manager_rest.resolver_with_catalog_support import (
    ResolverWithCatalogSupport
)
from manager_rest.storage import models, get_storage_manager
from manager_rest import config

REST_HOME_DIR = '/opt/manager'
REST_CONFIG_PATH = join(REST_HOME_DIR, 'cloudify-rest.conf')
REST_SECURITY_CONFIG_PATH = join(REST_HOME_DIR, 'rest-security.conf')
REST_AUTHORIZATION_CONFIG_PATH = join(REST_HOME_DIR, 'authorization.conf')

AT_LEAST = 'at_least'
BLUEPRINT_LINE = 'blueprint_line'
CURRENT_IMPORT_FROM = 'current_import_from'
CURRENT_IS_PINNED = 'current_is_pinned'
CURRENT_VERSION = 'current_version'
DEFAULT_TENANT = 'default_tenant'
END_POS = 'end_pos'
EXECUTORS = [DEPLOYMENT_PLUGINS_TO_INSTALL,
             WORKFLOW_PLUGINS_TO_INSTALL,
             HOST_AGENT_PLUGINS_TO_INSTALL]
FINE = 'fine'
IMPORT_FROM_MANAGED = 'managed'
IMPORT_FROM_SOURCE = 'source'
IMPORT_FROM_URL = 'url'
IMPORTS = 'imports'
IS_PINNED = True
IS_NOT_PINNED = False
IS_UNKNOWN = True
IS_NOT_UNKNOWN = False
PLUGIN_NAME = 'plugin_name'
REPLACEMENT = 'replacement'
EXACT_VERSION = 'exact_version'
START_POS = 'start_pos'
SUGGESTED_IMPORT_FROM = 'suggested_import_from'
SUGGESTED_IS_PINNED = 'suggested_is_pinned'
SUGGESTED_VERSION = 'suggested_version'
UNKNOWN = 'unknown'
UPDATES = 'updates'
VERSIONS = 'versions'
MAX_IMPORT_TOKEN_LENGTH = 200


class UpdateException(Exception):
    pass


CLOUDIFY_PLUGINS = {
    'cloudify-aws-plugin': {
        VERSIONS: sorted(['2.5.11', '2.4.4', '2.4.3', '2.4.2', '2.4.0',
                          '2.3.5', '2.3.4', '2.3.2', '2.3.1', '2.3.0',
                          '2.2.1', '2.2.0', '2.1.0', '2.0.2', '2.0.1',
                          '2.0.0', '1.5.1.2', '1.5.1.1', '1.5.1', '1.5'],
                         key=parse_version, reverse=True),
        EXACT_VERSION: None,
    },
    'cloudify-azure-plugin': {
        VERSIONS: sorted(['3.0.9', '3.0.4', '3.0.3', '3.0.2', '3.0.1', '3.0.0',
                          '2.1.10', '2.1.9', '2.1.8', '2.1.7', '2.1.6',
                          '2.1.5', '2.1.4', '2.1.3', '2.1.1', '2.1.0', '2.0.0',
                          '1.8.0', '1.7.3', '1.7.2', '1.7.1', '1.7.0', '1.6.2',
                          '1.6.1', '1.6.0', '1.5.1.1', '1.5.1', '1.5.0',
                          '1.4.3', '1.4.2', '1.4'],
                         key=parse_version, reverse=True),
    },
    'cloudify-gcp-plugin': {
        VERSIONS: sorted(['1.6.6', '1.6.5', '1.6.4', '1.6.2', '1.6.0', '1.5.1',
                          '1.5.0', '1.4.5', '1.4.4', '1.4.3', '1.4.2', '1.4.1',
                          '1.4.0', '1.3.0.1', '1.3.0', '1.2.0', '1.1.0',
                          '1.0.1'],
                         key=parse_version, reverse=True),
    },
    'cloudify-openstack-plugin': {
        VERSIONS: sorted(['2.14.22', '3.3.0', '3.2.21', '3.2.18', '3.2.17',
                          '2.14.20', '3.2.16', '2.14.19', '2.14.18', '3.2.15',
                          '3.2.14', '3.2.12', '3.2.11', '2.14.17', '3.2.10',
                          '2.14.16', '3.2.9', '2.14.15', '2.14.14', '2.14.13',
                          '3.2.8', '2.14.12', '3.2.7', '3.2.6', '3.2.5',
                          '3.2.4', '3.2.3', '2.14.11', '3.2.2', '3.2.1',
                          '2.14.10', '3.2.0', '3.1.1', '2.14.9', '3.1.0',
                          '3.0.0', '2.14.8', '2.14.7', '2.14.6', '2.14.5',
                          '2.14.4', '2.14.3', '2.14.2', '2.14.1', '2.14.0',
                          '2.13.1', '2.13.0', '2.12.0', '2.11.1', '2.11.0',
                          '2.10.0', '2.9.8', '2.9.6', '2.9.5', '2.9.4',
                          '2.9.3', '2.9.2', '2.9.1', '2.9.0', '2.8.2', '2.8.1',
                          '2.8.0', '2.7.6', '2.7.5', '2.7.2.1', '2.7.4',
                          '2.7.3', '2.7.2', '2.7.1', '2.7.0', '2.6.0', '2.5.3',
                          '2.5.2', '2.5.1', '2.5.0', '2.4.1.1', '2.4.1',
                          '2.4.0', '2.3.0', '2.2.0'],
                         key=parse_version, reverse=True),
    },
    'cloudify-vsphere-plugin': {
        VERSIONS: sorted(['2.19.1', '2.18.13', '2.18.11', '2.18.10', '2.18.9',
                          '2.18.8', '2.18.7', '2.18.6', '2.18.5', '2.18.4',
                          '2.18.3', '2.18.2', '2.18.1',  '2.18.0', '2.18.0',
                          '2.17.0', '2.16.2', '2.16.0',  '2.15.1', '2.15.0',
                          '2.14.0', '2.13.1', '2.13.0', '2.12.0', '2.9.3',
                          '2.11.0', '2.10.0', '2.9.2', '2.9.1', '2.9.0',
                          '2.8.0', '2.7.0', '2.6.1', '2.2.2', '2.6.0', '2.4.1',
                          '2.5.0', '2.4.0', '2.3.0'],
                         key=parse_version, reverse=True),
    },
    'cloudify-terraform-plugin': {
        VERSIONS: sorted(['0.15.1', '0.14.4', '0.13.4', '0.13.3', '0.13.2',
                          '0.13.1', '0.13.0', '0.12.0', '0.11.0', '0.10',
                          '0.9', '0.7'],
                         key=parse_version, reverse=True),
    },
    'cloudify-ansible-plugin': {
        VERSIONS: sorted(['2.10.1', '2.9.4', '2.9.3', '2.9.2', '2.9.1',
                          '2.9.0', '2.8.2', '2.8.1', '2.8.0', '2.7.1', '2.7.0',
                          '2.6.0', '2.5.0', '2.4.0', '2.3.0', '2.2.0', '2.1.1',
                          '2.1.0', '2.0.4', '2.0.3', '2.0.2', '2.0.1',
                          '2.0.0'],
                         key=parse_version, reverse=True),
    },
    'cloudify-kubernetes-plugin': {
        VERSIONS: sorted(['2.9.3', '2.8.3', '2.8.2', '2.8.1', '2.8.0', '2.7.2',
                          '2.7.1', '2.7.0', '2.6.5', '2.6.4', '2.6.3', '2.6.2',
                          '2.6.0', '2.5.0', '2.4.1', '2.4.0', '2.3.2', '2.3.1',
                          '2.3.0', '2.2.2', '2.2.1', '2.2.0', '2.1.0',
                          '2.0.0.1', '2.0.0', '1.4.0', '1.3.1.1', '1.3.1',
                          '1.3.0', '1.2.2', '1.2.1', '1.2.0', '1.1.0',
                          '1.0.0'],
                         key=parse_version, reverse=True),
    },
    'cloudify-docker-plugin': {
        VERSIONS: sorted(['2.0.3', '2.0.2', '2.0.1', '2.0.0', '1.3.2', '1.2',
                          '1.1'],
                         key=parse_version, reverse=True),
    },
    'cloudify-netconf-plugin': {
        VERSIONS: sorted(['0.4.4', '0.4.2', '0.4.1', '0.4.0', '0.3.1', '0.3.0',
                          '0.2.1', '0.2.0', '0.1.0'],
                         key=parse_version, reverse=True),
    },
    'cloudify-fabric-plugin': {
        VERSIONS: sorted(['2.0.7', '2.0.6', '2.0.5', '2.0.4', '2.0.3', '1.7.0',
                          '2.0.1', '2.0.0', '1.6.0', '1.5.3', '1.5.1', '1.5',
                          '1.4.3', '1.4.2', '1.4.1', '1.4', '1.3.1', '1.3',
                          '1.2.1', '1.2', '1.1'],
                         key=parse_version, reverse=True),
        AT_LEAST: '2.0.6',
    },
    'cloudify-libvirt-plugin': {
        VERSIONS: sorted(['0.9.0', '0.8.1', '0.8.0', '0.7.0', '0.6.0', '0.5.0',
                          '0.4.1', '0.4', '0.3', '0.2', '0.1'],
                         key=parse_version, reverse=True),
    },
    'cloudify-utilities-plugin': {
        VERSIONS: sorted(['1.24.1', '1.23.12', '1.23.7', '1.23.6', '1.23.5',
                          '1.23.4', '1.23.3', '1.23.2', '1.23.1', '1.23.0',
                          '1.22.1', '1.22.0', '1.21.0', '1.20.0', '1.19.0',
                          '1.18.0', '1.17.0', '1.16.1', '1.16.0', '1.15.3',
                          '1.15.2', '1.15.1', '1.15.0', '1.14.0', '1.13.0',
                          '1.12.5', '1.12.4', '1.12.3', '1.12.2', '1.12.1',
                          '1.12.0', '1.11.2', '1.10.2', '1.10.1', '1.10.0',
                          '1.9.8', '1.9.7', '1.9.6', '1.9.5', '1.9.4', '1.9.3',
                          '1.9.2', '1.9.1', '1.9.0', '1.8.3', '1.8.2', '1.8.1',
                          '1.8.0', '1.7.3', '1.7.2', '1.7.1', '1.7.0', '1.6.1',
                          '1.6.0', '1.5.4', '1.5.3', '1.5.2', '1.5.1',
                          '1.5.0.1', '1.5.0', '1.4.5', '1.4.4', '1.4.3',
                          '1.4.2.1', '1.4.2', '1.4.1.2', '1.4.1.1', '1.4.1',
                          '1.3.1', '1.3.0', '1.2.5', '1.2.4', '1.2.3', '1.2.2',
                          '1.2.1', '1.2.0', '1.1.1', '1.1.0', '1.0.0', ],
                         key=parse_version, reverse=True),
    },
    'cloudify-host-pool-plugin': {
        VERSIONS: sorted(['1.5.2', '1.5.1', '1.5', '1.4', '1.2', ],
                         key=parse_version, reverse=True),
    },
    'cloudify-diamond-plugin': {
        VERSIONS: sorted(['1.3.19', '1.3.18', '1.3.17', '1.3.16', '1.3.15',
                          '1.3.14', '1.3.10', '1.3.9', '1.3.8', '1.3.7',
                          '1.3.6', '1.3.5', '1.3.4', '1.3.3', '1.3.2', '1.3.1',
                          '1.3', '1.2.1', '1.2', '1.1'],
                         key=parse_version, reverse=True),
    },
    'tosca-vcloud-plugin': {
        VERSIONS: sorted(['1.6.1', '1.6.0', '1.5.1', '1.5.0', '1.4.1'],
                         key=parse_version, reverse=True),
    },
    'cloudify-vcloud-plugin': {
        VERSIONS: sorted(['2.0.0', ],
                         key=parse_version, reverse=True),
    },
    'cloudify-helm-plugin': {
        VERSIONS: sorted(['0.0.8', '0.0.7', ],
                         key=parse_version, reverse=True),
    },
}


def setup_environment():
    for value, envvar in [
            (REST_CONFIG_PATH, 'MANAGER_REST_CONFIG_PATH'),
            (REST_SECURITY_CONFIG_PATH, 'MANAGER_REST_SECURITY_CONFIG_PATH'),
    ]:
        if value is not None:
            environ[envvar] = value

    app = setup_flask_app()
    with app.app_context():
        config.instance.load_configuration()
    set_admin_current_user(app)


def blueprint_file_name(blueprint: models.Blueprint) -> str:
    return join(
        config.instance.file_server_root,
        FILE_SERVER_BLUEPRINTS_FOLDER,
        blueprint.tenant.name,
        blueprint.id,
        blueprint.main_file_name
    )


def archive_file_name(blueprint: models.Blueprint) -> str:
    for arc_type in SUPPORTED_ARCHIVE_TYPES:
        # attempting to find the archive file on the file system
        local_path = join(
            config.instance.file_server_root,
            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
            blueprint.tenant.name,
            blueprint.id,
            '{0}.{1}'.format(blueprint.id, arc_type))

        if isfile(local_path):
            archive_type = arc_type
            break
    else:
        raise UpdateException("Could not find blueprint's archive; "
                              "Blueprint ID: {0}".format(blueprint.id))
    return join(
        config.instance.file_server_root,
        FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
        blueprint.tenant.name,
        blueprint.id,
        '{0}.{1}'.format(blueprint.id, archive_type)
    )


def blueprint_updated_file_name(blueprint: models.Blueprint) -> str:
    base_file_name = '.'.join(blueprint.main_file_name.split('.')[:-1])
    index = 0
    updated_file_name = '{0}-new.yaml'.format(base_file_name)
    while exists(join(
            config.instance.file_server_root,
            FILE_SERVER_BLUEPRINTS_FOLDER,
            blueprint.tenant.name,
            blueprint.id,
            updated_file_name)):
        updated_file_name = '{0}-{1:02d}.yaml'.format(base_file_name, index)
        index += 1
    return join(
        config.instance.file_server_root,
        FILE_SERVER_BLUEPRINTS_FOLDER,
        blueprint.tenant.name,
        blueprint.id,
        updated_file_name
    )


def blueprint_diff_file_name(blueprint: models.Blueprint) -> str:
    base_file_name = '.'.join(blueprint.main_file_name.split('.')[:-1])
    index = 0
    diff_file_name = '{0}.diff'.format(base_file_name)
    while exists(join(
            config.instance.file_server_root,
            FILE_SERVER_BLUEPRINTS_FOLDER,
            blueprint.tenant.name,
            blueprint.id,
            diff_file_name)):
        diff_file_name = '{0}-{1:02d}.diff'.format(base_file_name, index)
        index += 1
    return join(
        config.instance.file_server_root,
        FILE_SERVER_BLUEPRINTS_FOLDER,
        blueprint.tenant.name,
        blueprint.id,
        diff_file_name
    )


def load_imports(blueprint: models.Blueprint) -> dict:
    file_name = blueprint_file_name(blueprint)
    try:
        with open(file_name, 'rb') as blueprint_file:
            try:
                return yaml.safe_load(blueprint_file)[IMPORTS]
            except yaml.YAMLError as ex:
                raise UpdateException(
                    'Cannot load imports from {0}: '
                    '{1}'.format(file_name, ex))
            except KeyError:
                raise UpdateException(
                    'Cannot find imports definition in {0}'.format(file_name))
    except (FileNotFoundError, PermissionError):
        raise UpdateException(
            'Blueprint file {0} cannot be read'.format(file_name))
    return []


def load_mappings(file_name: str) -> list:
    try:
        with open(file_name, 'r') as mapping_file:
            try:
                mappings = yaml.safe_load(mapping_file)
            except yaml.YAMLError as ex:
                raise UpdateException(
                    'Cannot load mappings from {0}: {1}'.format(file_name, ex))
    except (FileNotFoundError, PermissionError):
        raise UpdateException(
            'Mappings file {0} cannot be read'.format(file_name))
    return mappings


@lru_cache(maxsize=2048)
def spec_from_url(resolver: ResolverWithCatalogSupport, url: str) -> tuple:
    try:
        response_text = resolver.fetch_import(url)
    except dsl_parser_exceptions.DSLParsingLogicException as ex:
        print('Cannot retrieve {0}: {1}'.format(url, ex))
        return None, None
    try:
        plugin_yaml = yaml.safe_load(response_text)
    except yaml.YAMLError as ex:
        print('Cannot load imports from {0}: {1}'.format(url, ex))
        return None, None
    for _, spec in plugin_yaml.get('plugins', {}).items():
        if spec.get(PLUGIN_PACKAGE_NAME) and \
                spec.get(PLUGIN_PACKAGE_VERSION):
            return spec[PLUGIN_PACKAGE_NAME], \
                   spec[PLUGIN_PACKAGE_VERSION]
    return None, None


def spec_from_import(plugin_line: str) -> tuple:
    # More or less copy of ResolverWithCatalogSupport._resolve_plugin_yaml_url
    spec = plugin_line.replace('plugin:', '', 1).strip()
    name, _, params = spec.partition('?')
    for filter_name, filter_value in parse_qs(params).items():
        if filter_name == 'version':
            if len(filter_value) == 1:
                return name, filter_value[0].strip()
            return name, None
    return name, None


def plugin_spec(resolver: ResolverWithCatalogSupport,
                import_line: str) -> tuple:
    if import_line.startswith('http://') or \
            import_line.startswith('https://'):
        name, version = spec_from_url(resolver, import_line)
        if name and version:
            return IS_PINNED, IS_NOT_UNKNOWN, IMPORT_FROM_URL, name, version
        else:
            return IS_PINNED, IS_UNKNOWN, IMPORT_FROM_URL, None, None
    if import_line.startswith('plugin:'):
        name, version = spec_from_import(import_line)
        if version and version.startswith('>'):
            return IS_NOT_PINNED, IS_NOT_UNKNOWN, IMPORT_FROM_MANAGED, \
                   name, version
        if not version:
            return IS_NOT_PINNED, IS_NOT_UNKNOWN, IMPORT_FROM_MANAGED, \
                   name, version
        return IS_PINNED, IS_NOT_UNKNOWN, IMPORT_FROM_MANAGED, name, version
    return IS_NOT_PINNED, IS_UNKNOWN, IMPORT_FROM_SOURCE, None, None


def plugins_in_a_plan(plan: Plan) -> collections.Iterable:
    for executor in [DEPLOYMENT_PLUGINS_TO_INSTALL,
                     WORKFLOW_PLUGINS_TO_INSTALL,
                     HOST_AGENT_PLUGINS_TO_INSTALL]:
        if executor not in plan:
            continue
        for plugin in plan[executor]:
            if plugin[PLUGIN_PACKAGE_NAME] and \
                    plugin[PLUGIN_PACKAGE_VERSION]:
                yield plugin


def find_plugin_in_a_plan(plan: Plan, plugin_name: str) -> dict:
    for plugin in plugins_in_a_plan(plan):
        if plugin[PLUGIN_PACKAGE_NAME] == plugin_name:
            return plugin
    return {}


def suggest_version(plugin_name: str, plugin_version: str) -> str:
    if plugin_name not in CLOUDIFY_PLUGINS:
        return plugin_version
    if CLOUDIFY_PLUGINS[plugin_name].get(EXACT_VERSION) is not None:
        return CLOUDIFY_PLUGINS[plugin_name].get(EXACT_VERSION)
    elif CLOUDIFY_PLUGINS[plugin_name].get(AT_LEAST) and \
            (parse_version(CLOUDIFY_PLUGINS[plugin_name][AT_LEAST]) >
             parse_version(plugin_version)):
        base_version = CLOUDIFY_PLUGINS[plugin_name][AT_LEAST]
    else:
        base_version = plugin_version
    plugin_major_version = base_version.split('.')[0]
    for available_version in CLOUDIFY_PLUGINS[plugin_name][VERSIONS]:
        if available_version.split('.')[0] == plugin_major_version:
            return available_version
    return base_version


def scan_blueprint(resolver: ResolverWithCatalogSupport,
                   blueprint: models.Blueprint,
                   plugin_names: tuple) -> tuple:
    def add_mapping(genre: str, content: object):
        if genre not in mappings:
            mappings[genre] = []
        mappings[genre].append(content)

    def update_stats(current_import_from: str = None,
                     suggested_import_from: str = None,
                     current_is_pinned: bool = None,
                     suggested_is_pinned: bool = None):
        if current_import_from is not None:
            stats[CURRENT_IMPORT_FROM][current_import_from] += 1
        if suggested_import_from is not None:
            stats[SUGGESTED_IMPORT_FROM][suggested_import_from] += 1
        if current_is_pinned:
            stats[CURRENT_IS_PINNED] += 1
        if suggested_is_pinned:
            stats[SUGGESTED_IS_PINNED] += 1

    imports = load_imports(blueprint)
    mappings = {}
    plugins_install_suggestions = {}
    stats = {
        CURRENT_IMPORT_FROM: collections.defaultdict(lambda: 0),
        CURRENT_IS_PINNED: 0,
        SUGGESTED_IMPORT_FROM: collections.defaultdict(lambda: 0),
        SUGGESTED_IS_PINNED: 0,
    }

    for import_line in imports:
        if import_line.endswith('/types.yaml'):
            continue
        is_pinned_version, is_unknown, import_from, plugin_name, _ = \
            plugin_spec(resolver, import_line)
        if plugin_names and plugin_name not in plugin_names:
            continue
        update_stats(current_import_from=import_from,
                     current_is_pinned=is_pinned_version)
        if is_unknown:
            add_mapping(UNKNOWN, import_line)
            update_stats(suggested_import_from=import_from,
                         suggested_is_pinned=is_pinned_version)
            continue
        plugin_in_plan = find_plugin_in_a_plan(blueprint.plan, plugin_name)
        if not plugin_in_plan:
            update_stats(suggested_import_from=import_from,
                         suggested_is_pinned=is_pinned_version)
            continue
        suggested_version = suggest_version(
            plugin_name, plugin_in_plan[PLUGIN_PACKAGE_VERSION]
        )
        if not suggested_version:
            add_mapping(UNKNOWN, import_line)
            update_stats(suggested_import_from=import_from,
                         suggested_is_pinned=is_pinned_version)
            continue
        if plugin_name not in plugins_install_suggestions:
            plugins_install_suggestions[plugin_name] = suggested_version
        if not is_pinned_version:
            add_mapping(FINE, import_line)
            update_stats(suggested_import_from=import_from,
                         suggested_is_pinned=is_pinned_version)
            continue
        add_mapping(UPDATES, {
            import_line: {
                PLUGIN_NAME: plugin_name,
                CURRENT_VERSION: plugin_in_plan[PLUGIN_PACKAGE_VERSION],
                SUGGESTED_VERSION: suggested_version,
            }
        })
        update_stats(suggested_import_from=IMPORT_FROM_MANAGED,
                     suggested_is_pinned=False)
    return mappings, stats, plugins_install_suggestions


def get_imports(blueprint_file: typing.TextIO) -> dict:
    level = 0
    imports_token = None
    import_lines = {}
    blueprint_file.seek(0, 0)
    for t in yaml.scan(blueprint_file):
        if isinstance(t, (yaml.tokens.BlockMappingStartToken,
                          yaml.tokens.BlockSequenceStartToken,
                          yaml.tokens.FlowMappingStartToken,
                          yaml.tokens.FlowSequenceStartToken)):
            level += 1
        if isinstance(t, (yaml.tokens.BlockEndToken,
                          yaml.tokens.FlowMappingEndToken,
                          yaml.tokens.FlowSequenceEndToken)):
            level -= 1

        if isinstance(t, yaml.tokens.ScalarToken):
            if level == 1 and t.value == 'imports':
                imports_token = t
                continue

            token_length = t.end_mark.index - t.start_mark.index

            if level >= 1 and imports_token and \
                    token_length < MAX_IMPORT_TOKEN_LENGTH:
                import_lines[t.value] = {
                    START_POS: t.start_mark.index,
                    END_POS: t.end_mark.index,
                }

        if isinstance(t, yaml.tokens.KeyToken) and imports_token:
            break

    return import_lines


def write_updated_blueprint(input_file_name: str, output_file_name: str,
                            import_updates: list):
    try:
        with open(input_file_name, 'rb') as input_file:
            with open(output_file_name, 'wb') as output_file:
                for idx, update in enumerate(import_updates):
                    content = input_file.read(update[START_POS] -
                                              input_file.tell())
                    output_file.write(content)
                    output_file.write(update[REPLACEMENT].
                                      encode('utf-8', 'ignore'))
                    input_file.read(update[END_POS] - update[START_POS])
                content = input_file.read()
                output_file.write(content)
    except (FileNotFoundError, PermissionError) as ex:
        raise UpdateException('Cannot update blueprint file source {0}, '
                              'destination {1}: {2}'.format(
                                  input_file_name, output_file_name, ex))


def write_blueprint_diff(from_file_name: str, to_file_name: str,
                         diff_file_name: str):
    def file_mtime(path):
        t = datetime.fromtimestamp(stat(path).st_mtime,
                                   timezone.utc)
        return t.astimezone().isoformat()

    try:
        with open(from_file_name, 'r') as from_file:
            from_lines = from_file.readlines()
    except (FileNotFoundError, PermissionError) as ex:
        raise UpdateException('Cannot read a blueprint file {0}: {1}'.format(
                              from_file_name, ex))
    try:
        with open(to_file_name, 'r') as to_file:
            to_lines = to_file.readlines()
    except (FileNotFoundError, PermissionError) as ex:
        raise UpdateException('Cannot read a blueprint file {0}: {1}'.format(
                              from_file_name, ex))
    diff = difflib.context_diff(
        from_lines,
        to_lines,
        from_file_name,
        to_file_name,
        file_mtime(from_file_name),
        file_mtime(to_file_name)
    )
    try:
        with open(diff_file_name, 'w') as diff_file:
            diff_file.writelines(diff)
    except (FileNotFoundError, PermissionError) as ex:
        raise UpdateException('Cannot write a diff file {0}: {1}'.format(
                              diff_file_name, ex))
    print('An diff file was generated for your change: {0}'.format(
          diff_file_name))


def update_archive(blueprint: models.Blueprint, updated_file_name: str):
    def format_from_file_name(file_name: str) -> str:
        file_name_split = file_name.split('.')
        if file_name_split[-1].upper() == 'ZIP':
            return 'zip'
        if file_name_split[-1].upper() == 'TAR':
            return 'tar'
        if file_name_split[-1].upper() == 'TBZ2' or \
                (file_name_split[-2].upper() == 'TAR' and
                 file_name_split[-1].upper() == 'BZ2'):
            return 'bztar'
        if file_name_split[-1].upper() == 'TGZ' or \
                (file_name_split[-2].upper() == 'TAR' and
                 file_name_split[-1].upper() == 'GZ'):
            return 'gztar'

    blueprint_archive_file_name = archive_file_name(blueprint)
    archive_format = format_from_file_name(blueprint_archive_file_name)
    if not archive_format:
        raise UpdateException('Unknown archive format: {0}'.format(
            blueprint_archive_file_name))
    with TemporaryDirectory() as working_dir:
        os.chdir(working_dir)
        shutil.unpack_archive(blueprint_archive_file_name, working_dir)
        archive_base_dir = os.listdir(working_dir)[0]
        shutil.copy(updated_file_name,
                    join(working_dir,
                         archive_base_dir,
                         blueprint.main_file_name))
        new_archive_base = mktemp()
        new_archive_file_name = shutil.make_archive(new_archive_base,
                                                    archive_format,
                                                    root_dir=working_dir)
        move(new_archive_file_name, blueprint_archive_file_name)
        chmod(blueprint_archive_file_name, 0o644)


def correct_blueprint(blueprint: models.Blueprint,
                      plugin_names: tuple,
                      mappings: dict) -> str:
    def line_replacement(mapping_spec: dict) -> str:
        suggested_version = mapping_spec.get(SUGGESTED_VERSION)
        next_major_version = int(suggested_version.split('.')[0]) + 1
        return 'plugin:{0}?version=>={1},<{2}'.format(
            mapping_spec.get(PLUGIN_NAME),
            suggested_version,
            next_major_version)

    if not mappings:
        return UNKNOWN
    if not mappings.get(UPDATES):
        if mappings.get(UNKNOWN):
            return UNKNOWN
        else:
            return FINE
    file_name = blueprint_file_name(blueprint)
    new_file_name = blueprint_updated_file_name(blueprint)
    try:
        with open(file_name, 'rb') as blueprint_file:
            import_lines = get_imports(blueprint_file)
    except (FileNotFoundError, PermissionError) as ex:
        raise UpdateException('Cannot load blueprint from {0}: {1}'.format(
            file_name, ex))
    import_updates = []
    for mapping_updates in mappings.get(UPDATES):
        for blueprint_line, spec in mapping_updates.items():
            if blueprint_line not in import_lines:
                continue
            if plugin_names and spec.get(PLUGIN_NAME) not in plugin_names:
                continue
            import_updates.append({
                REPLACEMENT: line_replacement(spec),
                START_POS: import_lines[blueprint_line][START_POS],
                END_POS: import_lines[blueprint_line][END_POS],
            })

    write_updated_blueprint(
        file_name, new_file_name,
        sorted(import_updates, key=lambda u: u[START_POS])
    )
    write_blueprint_diff(file_name, new_file_name,
                         blueprint_diff_file_name(blueprint))
    update_archive(blueprint, new_file_name)
    move(new_file_name, file_name)
    return UPDATES


def printout_scanning_stats(total_blueprints: int,
                            mappings: dict,
                            stats: dict):
    number_of_unknown_or_updates = len([b for b in mappings.values()
                                        if UPDATES in b or UNKNOWN in b])
    number_of_unknown = len([b for b in mappings.values()
                             if UNKNOWN in b])
    pinned = (sum(s.get(CURRENT_IS_PINNED) for s in stats.values()),
              sum(s.get(SUGGESTED_IS_PINNED) for s in stats.values()))
    url_import = (sum(s.get(CURRENT_IMPORT_FROM, {}).
                      get(IMPORT_FROM_URL, 0) for s in stats.values()),
                  sum(s.get(SUGGESTED_IMPORT_FROM, {}).
                      get(IMPORT_FROM_URL, 0) for s in stats.values()))
    source_import = (sum(s.get(CURRENT_IMPORT_FROM, {}).
                         get(IMPORT_FROM_SOURCE, 0) for s in stats.values()),
                     sum(s.get(SUGGESTED_IMPORT_FROM, {}).
                         get(IMPORT_FROM_SOURCE, 0) for s in stats.values()))
    print('\n\n                             SCANNING STATS')
    print('----------------------------------------------+---------------')
    print(' Number blueprints scanned                    | {0:14d}'.
          format(total_blueprints))
    print('                                              +---------------')
    print('                                              | BEFORE | AFTER')
    print('----------------------------------------------+--------+------')
    print(' Number of blueprints with one or more issues | {0:6d} | {1:5d}'.
          format(number_of_unknown_or_updates, number_of_unknown))
    print(' Number of blueprints with version lock       | {0:6d} | {1:5d}'.
          format(pinned[0], pinned[1]))
    print(' Number of blueprints with URL import         | {0:6d} | {1:5d}'.
          format(url_import[0], url_import[1]))
    print(' Number of blueprints with source import      | {0:6d} | {1:5d}'.
          format(source_import[0], source_import[1]))
    if source_import[1] > 0:
        # There are some plugins that are imported from source
        print('\nWARNING! There will be still some plugins imported from '
              'source left.\n         Those are listed in mappings '
              'file under the `unknown` nodes.\n         Please verify that '
              'you can replace those with managed plugins\n         and edit '
              'generated mappings file accordingly.')


def printout_install_suggestions(install_suggestions: dict):
    print('\n\nMake sure those plugins are installed (in suggested versions):')
    for plugin_name, suggested_versions in install_suggestions.items():
        print('  {0}: {1}'.format(plugin_name, ', '.join(suggested_versions)))


def printout_correction_stats(stats):
    total_blueprints_scanned = sum([len(s) for s in stats.values()])
    number_of_unknown = len(stats.get(UNKNOWN, []))

    # Collect: the number of blueprints scanned,
    #          the number of blueprints corrected,
    #          the number of blueprints that are now valid (total)
    #          the number of blueprints that still require manual attention !!!

    print('\n\n                   CORRECTION STATS')
    print('----------------------------------------------+-------')
    print(' Number blueprints scanned                    | {0:5d}'.
          format(total_blueprints_scanned))
    print('----------------------------------------------+-------')
    print(' Number of blueprints corrected               | {0:5d}'.
          format(len(stats.get(UPDATES, []))))
    print(' Number of blueprints that are valid          | {0:5d}'.
          format(len(stats.get(UPDATES, [])) + len(stats.get(FINE, []))))
    print(' Number of blueprints that require attention  | {0:5d}'.
          format(number_of_unknown))
    if number_of_unknown:
        print('\n\nMake sure to manually attend to {0} more '
              'blueprints'.format(number_of_unknown))
        if number_of_unknown < 20:
            print('These blueprints require manual attention: {0}'.format(
                ', '.join(stats.get(UNKNOWN, []))))


@click.command()
@click.option('-t', '--tenant-name', 'tenant_names', multiple=True,
              help='Tenant name; mutually exclusivele with --all-tenants.', )
@click.option('-a', '--all-tenants', is_flag=True,
              help='Include resources from all tenants.', )
@click.option('--plugin-name', 'plugin_names',
              multiple=True, help='Plugin(s) to update (you can provide '
                                  'multiple --plugin-name(s).')
@click.option('-b', '--blueprint', 'blueprint_ids',
              multiple=True, help='Blueprint(s) to update (you can provide '
                                  'multiple --blueprint(s).')
@click.option('--mapping', 'mapping_file', multiple=False, required=True,
              help='Provide a mapping file generated with ')
@click.option('--correct', is_flag=True, default=False,
              help='Update the blueprints using provided mapping file.')
def main(tenant_names, all_tenants, plugin_names, blueprint_ids,
         mapping_file, correct):
    def update_suggestions(new_suggestion: dict):
        for plugin_name, plugin_version in new_suggestion.items():
            if plugin_name not in install_suggestions:
                install_suggestions[plugin_name] = []
            if plugin_version not in install_suggestions[plugin_name]:
                install_suggestions[plugin_name].append(plugin_version)

    if all_tenants and tenant_names:
        print('--all-tenants and --tenant-name options are mutually exclusive')
        exit(1)
    if not tenant_names:
        tenant_names = (DEFAULT_TENANT,)

    setup_environment()
    set_tenant_in_app(get_tenant_by_name(DEFAULT_TENANT))
    sm = get_storage_manager()

    # Prepare the resolver
    cloudify_section = sm.get(models.ProviderContext, PROVIDER_CONTEXT_ID).\
        context.get(CLOUDIFY, {})
    resolver_section = cloudify_section.get(IMPORT_RESOLVER_KEY, {})
    resolver_section.setdefault(
        'implementation',
        'manager_rest.'
        'resolver_with_catalog_support:ResolverWithCatalogSupport')
    resolver = dsl_parser_utils.create_import_resolver(resolver_section)

    if all_tenants:
        tenants = sm.list(models.Tenant, get_all_results=True)
    else:
        tenants = [get_tenant_by_name(name) for name in tenant_names]
    blueprint_filter = {'tenant': None}
    if blueprint_ids:
        blueprint_filter['id'] = blueprint_ids

    mappings = load_mappings(mapping_file) if correct else {}
    stats, install_suggestions, blueprints_processed = {}, {}, 0

    for tenant in tenants:
        set_tenant_in_app(get_tenant_by_name(tenant.name))
        sm = get_storage_manager()
        blueprint_filter['tenant'] = tenant
        blueprints = sm.list(
            models.Blueprint,
            filters=blueprint_filter,
            get_all_results=True
        )

        for blueprint in blueprints:
            print('Processing blueprint of {0}: {1} '.format(tenant.name,
                                                             blueprint.id))
            blueprint_identifier = '{0}::{1}'.format(tenant.name, blueprint.id)
            if correct:
                try:
                    result = correct_blueprint(
                        blueprint,
                        plugin_names,
                        mappings.get(tenant.name, {}).get(blueprint.id)
                    )
                except UpdateException as ex:
                    print(ex)
                else:
                    blueprints_processed += 1
                    if result not in stats:
                        stats[result] = [blueprint_identifier]
                    else:
                        stats[result].append(blueprint_identifier)
            else:
                try:
                    a_mapping, a_statistic, a_suggestion = \
                        scan_blueprint(resolver, blueprint, plugin_names)
                except UpdateException as ex:
                    print(ex)
                else:
                    blueprints_processed += 1
                    if a_mapping:
                        if tenant.name not in mappings:
                            mappings[tenant.name] = {}
                        mappings[tenant.name][blueprint.id] = a_mapping
                    if a_statistic:
                        stats[blueprint_identifier] = a_statistic
                    if a_suggestion:
                        update_suggestions(a_suggestion)

    # Wrap it up
    if correct:
        printout_correction_stats(stats)
    else:
        with open(mapping_file, 'w') as output_file:
            yaml.dump(mappings, output_file, default_flow_style=False)
        chmod(mapping_file, 0o644)
        print('\nSaved mapping file to the {0}'.format(mapping_file))
        printout_scanning_stats(blueprints_processed, mappings, stats)
        printout_install_suggestions(install_suggestions)


if __name__ == '__main__':
    main()

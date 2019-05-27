#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
#

import os
import sys

from uuid import uuid4

from flask_restful_swagger import swagger

from manager_rest import (
    manager_exceptions,
    utils,
)
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest import (
    rest_decorators,
    rest_utils,
)
from manager_rest.rest.responses_v2 import ListResponse
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import (
    get_storage_manager,
    models,
)
from manager_rest.upload_manager import (
    UploadedPluginsManager,
    UploadedCaravanManager,
)
from manager_rest.utils import create_filter_params_list_description
from manager_rest.constants import (INSTALLING_PREFIX,
                                    FILE_SERVER_PLUGINS_FOLDER,
                                    FILE_SERVER_RESOURCES_FOLDER
                                    )


class Plugins(SecuredResource):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.Plugin.__name__),
        nickname="listPlugins",
        notes='Returns a plugins list for the optionally provided '
              'filter parameters: {0}'.format(models.Plugin),
        parameters=create_filter_params_list_description(
            models.Plugin.response_fields,
            'plugins'
        )
    )
    @rest_decorators.exceptions_handled
    @authorize('plugin_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Plugin)
    @rest_decorators.create_filters(models.Plugin)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Plugin)
    @rest_decorators.all_tenants
    @rest_decorators.search('package_name')
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, all_tenants=None, search=None, **kwargs):
        """
        List uploaded plugins
        """

        return get_storage_manager().list(
            models.Plugin,
            include=_include,
            filters=filters,
            substr_filters=search,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants
        )

    @swagger.operation(
        responseClass=models.Plugin,
        nickname='upload',
        notes='Submitted plugin should be an archive containing the directory '
              ' which contains the plugin wheel. The supported archive type '
              'is: {archive_type}. The archive may be submitted via either'
              ' URL or by direct upload. Archive wheels must contain a '
              'module.json file containing required metadata for the plugin '
              'usage.'
        .format(archive_type='tar.gz'),
        parameters=[{'name': 'plugin_archive_url',
                     'description': 'url of a plugin archive file',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query'},
                    {'name': 'body',
                     'description': 'Binary form of the tar '
                                    'gzipped plugin directory',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'binary',
                     'paramType': 'body'}],
        consumes=["application/octet-stream"]
    )
    @rest_decorators.exceptions_handled
    @authorize('plugin_upload')
    @rest_decorators.marshal_with(models.Plugin)
    def post(self, **kwargs):
        """
        Upload a plugin
        """
        storage_manager = get_storage_manager()
        is_caravan = False
        installed_plugins = []
        get_resource_manager().assert_no_snapshot_creation_running_or_queued()
        try:
            plugins, code = UploadedCaravanManager().receive_uploaded_data(
                **kwargs)
            is_caravan = True
        except UploadedCaravanManager.InvalidCaravanException:
            plugin, code = UploadedPluginsManager().receive_uploaded_data(
                str(uuid4()),
                **kwargs
            )
            plugins = [plugin]
        for plugin in plugins:
            try:
                get_resource_manager().install_plugin(plugin)
                installed_plugins.append(plugin)
            except manager_exceptions.ExecutionTimeout:
                tp, ex, tb = sys.exc_info()
                if not is_caravan:
                    raise manager_exceptions.PluginInstallationTimeout(
                        'Timed out during plugin installation.'
                        '({0}: {1})'.format(tp.__name__, ex)), None, tb
            except Exception:
                get_resource_manager().remove_plugin(plugin_id=plugin.id,
                                                     force=True)
                tp, ex, tb = sys.exc_info()
                if not is_caravan:
                    raise manager_exceptions.PluginInstallationError(
                        'Failed during plugin installation.'
                        '({0}: {1})'.format(tp.__name__, ex)), None, tb

        if is_caravan:
            storage_plugins = storage_manager.list(
                models.Plugin,
                filters={'id': [p.id for p in installed_plugins]})

            return ListResponse(items=storage_plugins.items,
                                metadata=storage_plugins.metadata), code
        else:
            return plugins[0], code


class PluginsArchive(SecuredResource):
    """
    GET = download previously uploaded plugin package.
    """
    @swagger.operation(
        responseClass='archive file',
        nickname="downloadPlugin",
        notes="download a plugin archive according to the plugin ID. "
    )
    @rest_decorators.exceptions_handled
    @authorize('plugin_download')
    def get(self, plugin_id, **kwargs):
        """
        Download plugin archive
        """
        # Verify plugin exists.
        plugin = get_storage_manager().get(models.Plugin, plugin_id)
        # While installing a plugin we add an `installing` prefix to the
        # archive_name, since the archive is saved without this prefix we
        # remove it before searching for the archive in the file system.
        archive_name = (plugin.archive_name[11:] if INSTALLING_PREFIX
                        in plugin.archive_name else plugin.archive_name)
        # attempting to find the archive file on the file system
        local_path = utils.get_plugin_archive_path(plugin_id, archive_name)
        if not os.path.isfile(local_path):
            raise RuntimeError("Could not find plugins archive; "
                               "Plugin ID: {0}".format(plugin_id))

        plugin_path = '{0}/{1}/{2}/{3}'.format(
            FILE_SERVER_RESOURCES_FOLDER,
            FILE_SERVER_PLUGINS_FOLDER,
            plugin_id,
            archive_name)

        return rest_utils.make_streaming_response(
            plugin_id,
            plugin_path,
            os.path.getsize(local_path),
            'tar.gz'
        )


class PluginsId(SecuredResource):
    @swagger.operation(
        responseClass=models.Plugin,
        nickname="getById",
        notes="Returns a plugin according to its ID."
    )
    @rest_decorators.exceptions_handled
    @authorize('plugin_get')
    @rest_decorators.marshal_with(models.Plugin)
    def get(self, plugin_id, _include=None, **kwargs):
        """
        Returns plugin by ID
        """
        return get_storage_manager().get(
            models.Plugin,
            plugin_id,
            include=_include
        )

    @swagger.operation(
        responseClass=models.Plugin,
        nickname="deleteById",
        notes="deletes a plugin according to its ID."
    )
    @rest_decorators.exceptions_handled
    @authorize('plugin_delete')
    @rest_decorators.marshal_with(models.Plugin)
    def delete(self, plugin_id, **kwargs):
        """
        Delete plugin by ID
        """
        return get_resource_manager().remove_plugin(plugin_id=plugin_id,
                                                    force=False)

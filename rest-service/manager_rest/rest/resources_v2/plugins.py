from datetime import datetime
import os
import shutil
import tempfile

from flask import request
from flask_restful.reqparse import Argument
from flask_restful.inputs import boolean

from cloudify.zip_utils import make_zip64_archive
from manager_rest import manager_exceptions
from manager_rest import upload_manager
from manager_rest.persistent_storage import get_storage_handler
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest import (
    rest_decorators,
    rest_utils,
    swagger,
)
from manager_rest.rest.responses_v2 import ListResponse
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import (
    authorize,
    check_user_action_allowed,
)
from manager_rest.storage import (
    get_storage_manager,
    models,
)
from manager_rest.utils import create_filter_params_list_description
from manager_rest.constants import FILE_SERVER_PLUGINS_FOLDER


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
    @authorize('plugin_upload')
    @rest_decorators.marshal_with(models.Plugin)
    def post(self, **kwargs):
        """Upload a plugin"""
        sm = get_storage_manager()
        resource_manager = get_resource_manager()

        args = rest_utils.get_args_and_verify_arguments([
            Argument('title'),
            Argument('private_resource', type=boolean),
            Argument('visibility'),
            Argument('uploaded_at'),
            Argument('created_by'),
        ])

        created_by = args.created_by
        if created_by:
            check_user_action_allowed('set_owner', None, True)
            created_by = rest_utils.valid_user(created_by)

        resource_manager.assert_no_snapshot_creation_running_or_queued()
        plugins = []
        wagon_infos = upload_manager.upload_plugin(**kwargs)
        for wagon_info in wagon_infos:
            plugin_id = wagon_info['id']
            visibility = resource_manager.get_resource_visibility(
                models.Plugin,
                plugin_id,
                args.visibility,
                args.private_resource,
            )
            build_props = wagon_info.get('build_server_os_properties') or {}
            plugin = models.Plugin(
                id=plugin_id,
                title=args.title or wagon_info.get('package_name'),
                package_name=wagon_info.get('package_name'),
                package_version=wagon_info.get('package_version'),
                archive_name=wagon_info.get('archive_name'),
                package_source=wagon_info.get('package_source'),
                supported_platform=wagon_info.get('supported_platform'),
                distribution=build_props.get('distribution'),
                distribution_version=build_props.get('distribution_version'),
                distribution_release=build_props.get('distribution_release'),
                wheels=wagon_info.get('wheels') or [],
                excluded_wheels=wagon_info.get('excluded_wheels'),
                supported_py_versions=wagon_info.get(
                    'supported_python_versions'),
                uploaded_at=args.uploaded_at or datetime.utcnow(),
                visibility=visibility,
                blueprint_labels=wagon_info.get('blueprint_labels'),
                labels=wagon_info.get('labels'),
                resource_tags=wagon_info.get('resource_tags'),
                creator=created_by,
            )
            sm.put(plugin)
            plugins.append(plugin)

        if len(plugins) > 1:
            return ListResponse(
                items=plugins,
                metadata={
                    'pagination': {
                        'total': len(plugins),
                        'size': len(plugins),
                        'offset': 0,
                    },
                }), 201
        return plugins[0], 201


class PluginsArchive(SecuredResource):
    """
    GET = download previously uploaded plugin package.
    """
    @swagger.operation(
        responseClass='archive file',
        nickname="downloadPlugin",
        notes="download a plugin archive according to the plugin ID. "
    )
    @authorize('plugin_download')
    def get(self, plugin_id, **kwargs):
        """
        Download plugin archive
        """
        # Verify plugin exists.
        plugin = get_storage_manager().get(models.Plugin, plugin_id)

        storage = get_storage_handler()
        base_path = os.path.join(FILE_SERVER_PLUGINS_FOLDER, plugin_id)

        if request.args.get('full_archive'):
            archive_path = os.path.join(base_path, 'plugin_archive.zip')

            try:
                storage.find(archive_path)
                archive_exists = True
            except manager_exceptions.NotFoundError:
                archive_exists = False

            if not archive_exists:
                tempdir = tempfile.mkdtemp()
                try:
                    temp_archive_dir = os.path.join(tempdir, 'archive')
                    os.makedirs(temp_archive_dir)
                    temp_zip_path = os.path.join(tempdir,
                                                 'plugin_archive.zip')

                    for fileinfo in storage.list(base_path):
                        path = fileinfo.filepath
                        dest = os.path.join(temp_archive_dir,
                                            os.path.split(path)[1])
                        with storage.get(path) as retrieved:
                            shutil.copy(retrieved, dest)

                    make_zip64_archive(temp_zip_path, temp_archive_dir)
                    storage.move(temp_zip_path, archive_path)
                finally:
                    shutil.rmtree(tempdir)
            return storage.proxy(archive_path)
        else:
            plugin_path = os.path.join(base_path, plugin.archive_name)
            return storage.proxy(plugin_path)


class PluginsId(SecuredResource):
    @swagger.operation(
        responseClass=models.Plugin,
        nickname="getById",
        notes="Returns a plugin according to its ID."
    )
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
    @authorize('plugin_delete')
    @rest_decorators.marshal_with(models.Plugin)
    def delete(self, plugin_id, **kwargs):
        """Delete plugin by ID"""
        get_resource_manager().remove_plugin(plugin_id=plugin_id, force=False)
        return None, 204

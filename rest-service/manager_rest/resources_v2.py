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
#
import shutil
import os
import json
import tarfile
from uuid import uuid4
from datetime import datetime

from flask_securest.rest_security import SecuredResource

from flask_restful_swagger import swagger
from flask import request

from manager_rest import resources
from manager_rest.resources import (marshal_with,
                                    exceptions_handled,
                                    verify_and_convert_bool,
                                    verify_parameter_in_request_body,
                                    verify_json_content_type,
                                    make_streaming_response)
from manager_rest import models
from manager_rest import responses_v2
from manager_rest import manager_exceptions
from manager_rest import config
from manager_rest import files
from manager_rest.storage_manager import get_storage_manager
from manager_rest.blueprints_manager import get_blueprints_manager
from manager_rest.blueprints_manager import \
    TRANSIENT_WORKERS_MODE_ENABLED_DEFAULT


def paginate(func):
    """
    Decorator for adding pagination
    """
    def verify_and_create_pagination_params(*args, **kw):
        offset = request.args.get("_offset")
        page_size = request.args.get("_size")
        pagination_params = {}
        if offset:
            pagination_params["offset"] = int(offset)
        if offset:
            pagination_params["page_size"] = int(page_size)
        return func(pagination=pagination_params, *args, **kw)
    return verify_and_create_pagination_params


def verify_and_create_filters(fields):
    """
    Decorator for extracting filter parameters from the request arguments and
    verifying their validity according to the provided fields.
    :param fields: a set of valid filter fields.
    :return: a Decorator for creating and validating the accepted fields.
    """
    def verify_and_create_filters_dec(f):
        def verify_and_create(*args, **kw):
            filters = {}
            args_without_meta_keys = \
                [(k, v) for (k, v) in request.args.iteritems(multi=True)
                 if not k.startswith('_')]
            for k, v in args_without_meta_keys:
                if k in filters:
                    filters[k].append(v)
                else:
                    filters[k] = [v]
            unknowns = [k for k in filters.iterkeys() if k not in fields]
            if unknowns:
                raise manager_exceptions.BadParametersError(
                    'Filter keys \'{key_names}\' do not exist. Allowed '
                    'filters are: {fields}'
                    .format(key_names=unknowns, fields=list(fields)))
            return f(filters=filters, *args, **kw)
        return verify_and_create
    return verify_and_create_filters_dec


def _create_filter_params_list_description(parameters, list_type):
    return [{'name': filter_val,
             'description': 'List {type} matching the \'{filter}\' '
                            'filter value'.format(type=list_type,
                                                  filter=filter_val),
             'required': False,
             'allowMultiple': False,
             'dataType': 'string',
             'defaultValue': None,
             'paramType': 'query'} for filter_val in parameters]


def _get_snapshot_path(snapshot_id):
    return os.path.join(
        config.instance().file_server_root,
        config.instance().file_server_snapshots_folder,
        snapshot_id
    )


class UploadedSnapshotsManager(files.UploadedDataManager):

    def _get_kind(self):
        return 'snapshot'

    def _get_data_url_key(self):
        return 'snapshot_archive_url'

    def _get_target_dir_path(self):
        return config.instance().file_server_snapshots_folder

    def _get_archive_type(self, archive_path):
        return 'zip'

    def _prepare_and_process_doc(self, data_id, file_server_root,
                                 archive_target_path):
        return get_blueprints_manager().create_snapshot_model(
            data_id,
            status=models.Snapshot.UPLOADED
        ), None


class Snapshots(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(responses_v2.Snapshot.__name__),
        nickname='list',
        notes='Returns a list of existing snapshots.'
    )
    @exceptions_handled
    @marshal_with(responses_v2.Snapshot)
    def get(self, _include=None, filters=None, pagination=None, **kwargs):
        return get_blueprints_manager().snapshots_list(include=_include,
                                                       filters=filters,
                                                       pagination=pagination)


class SnapshotsId(SecuredResource):

    @swagger.operation(
        responseClass=responses_v2.Snapshot,
        nickname='getById',
        notes='Returns a snapshot by its id.'
    )
    @exceptions_handled
    @marshal_with(responses_v2.Snapshot)
    def get(self, snapshot_id, _include=None, **kwargs):
        return get_blueprints_manager().get_snapshot(snapshot_id,
                                                     include=_include)

    @swagger.operation(
        responseClass=responses_v2.Snapshot,
        nickname='createSnapshot',
        notes='Create a new snapshot of the manager.',
        consumes=[
            "application/json"
        ]
    )
    @exceptions_handled
    @marshal_with(responses_v2.Execution)
    def put(self, snapshot_id):
        verify_json_content_type()
        request_json = request.json
        include_metrics = verify_and_convert_bool(
            'include_metrics',
            request_json.get('include_metrics', 'false')
        )
        include_credentials = verify_and_convert_bool(
            'include_credentials',
            request_json.get('include_credentials', 'true')
        )

        execution = get_blueprints_manager().create_snapshot(
            snapshot_id,
            include_metrics,
            include_credentials
        )
        return execution, 201

    @swagger.operation(
        responseClass=responses_v2.Snapshot,
        nickname='deleteSnapshot',
        notes='Delete existing snapshot.'
    )
    @exceptions_handled
    @marshal_with(responses_v2.Snapshot)
    def delete(self, snapshot_id):
        snapshot = get_blueprints_manager().delete_snapshot(snapshot_id)
        path = _get_snapshot_path(snapshot_id)
        shutil.rmtree(path, ignore_errors=True)
        return snapshot, 200

    @exceptions_handled
    def patch(self, snapshot_id):
        """
        Update snapshot status by id
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('status', request_json)

        get_blueprints_manager().update_snapshot_status(
            snapshot_id,
            request_json['status'],
            request_json.get('error', ''))


class SnapshotsIdArchive(SecuredResource):

    @swagger.operation(
        responseClass=responses_v2.Snapshot,
        nickname='uploadSnapshot',
        notes='Submitted snapshot should be an archive.'
              'Archive format has to be zip.'
              ' Snapshot archive may be submitted via either URL or by '
              'direct upload.',
        parameters=[{
            'name': 'snapshot_archive_url',
            'description': 'url of a snapshot archive file',
            'required': False,
            'allowMultiple': False,
            'dataType': 'string',
            'paramType': 'query'
        }, {
            'name': 'body',
            'description': 'Binary form of the zip',
            'required': True,
            'allowMultiple': False,
            'dataType': 'binary',
            'paramType': 'body'}],
        consumes=[
            "application/octet-stream"
        ]
    )
    @exceptions_handled
    @marshal_with(responses_v2.Snapshot)
    def put(self, snapshot_id):
        return UploadedSnapshotsManager().receive_uploaded_data(snapshot_id)

    @swagger.operation(
        nickname='downloadSnapshot',
        notes='Downloads snapshot as an archive.'
    )
    @exceptions_handled
    def get(self, snapshot_id):
        get_blueprints_manager().get_snapshot(snapshot_id)

        snapshot_path = os.path.join(
            _get_snapshot_path(snapshot_id),
            '{0}.zip'.format(snapshot_id)
        )

        snapshot_uri = '{0}/{1}/{2}/{2}.zip'.format(
            config.instance().file_server_resources_uri,
            config.instance().file_server_snapshots_folder,
            snapshot_id
        )

        return make_streaming_response(
            snapshot_id,
            snapshot_uri,
            os.path.getsize(snapshot_path),
            'zip'
        )


class SnapshotsIdRestore(SecuredResource):
    @swagger.operation(
        responseClass=responses_v2.Snapshot,
        nickname='restoreSnapshot',
        notes='Restore existing snapshot.'
    )
    @exceptions_handled
    @marshal_with(responses_v2.Snapshot)
    def post(self, snapshot_id):
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('recreate_deployments_envs',
                                         request_json)
        recreate_deployments_envs = verify_and_convert_bool(
            'recreate_deployments_envs',
            request_json['recreate_deployments_envs']
        )
        execution = get_blueprints_manager().restore_snapshot(
            snapshot_id,
            recreate_deployments_envs
        )
        return execution, 200


class Blueprints(resources.Blueprints):
    @swagger.operation(
        responseClass='List[{0}]'.format(responses_v2.BlueprintState.__name__),
        nickname="list",
        notes='Returns a list of submitted blueprints for the optionally '
              'provided filter parameters {0}'
        .format(models.BlueprintState.fields),
        parameters=_create_filter_params_list_description(
            models.BlueprintState.fields,
            'blueprints'
        )
    )
    @exceptions_handled
    @marshal_with(responses_v2.BlueprintState)
    @verify_and_create_filters(models.BlueprintState.fields)
    @paginate
    def get(self, _include=None, filters=None, pagination=None, **kwargs):
        """
        List uploaded blueprints
        """
        return get_blueprints_manager().blueprints_list(
            include=_include, filters=filters, pagination=pagination)


class BlueprintsId(resources.BlueprintsId):

    @swagger.operation(
        responseClass=responses_v2.BlueprintState,
        nickname="getById",
        notes="Returns a blueprint by its id."
    )
    @exceptions_handled
    @marshal_with(responses_v2.BlueprintState)
    def get(self, blueprint_id, _include=None, **kwargs):
        """
        Get blueprint by id
        """
        with resources.skip_nested_marshalling():
            return super(BlueprintsId, self).get(blueprint_id=blueprint_id,
                                                 _include=_include,
                                                 **kwargs)

    @swagger.operation(
        responseClass=responses_v2.BlueprintState,
        nickname="upload",
        notes="Submitted blueprint should be an archive "
              "containing the directory which contains the blueprint. "
              "Archive format may be zip, tar, tar.gz or tar.bz2."
              " Blueprint archive may be submitted via either URL or by "
              "direct upload.",
        parameters=[{'name': 'application_file_name',
                     'description': 'File name of yaml '
                                    'containing the "main" blueprint.',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query',
                     'defaultValue': 'blueprint.yaml'},
                    {'name': 'blueprint_archive_url',
                     'description': 'url of a blueprint archive file',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query'},
                    {
                        'name': 'body',
                        'description': 'Binary form of the tar '
                                       'gzipped blueprint directory',
                        'required': True,
                        'allowMultiple': False,
                        'dataType': 'binary',
                        'paramType': 'body'}],
        consumes=[
            "application/octet-stream"
        ]

    )
    @exceptions_handled
    @marshal_with(responses_v2.BlueprintState)
    def put(self, blueprint_id, **kwargs):
        """
        Upload a blueprint (id specified)
        """
        with resources.skip_nested_marshalling():
            return super(BlueprintsId, self).put(blueprint_id=blueprint_id,
                                                 **kwargs)

    @swagger.operation(
        responseClass=responses_v2.BlueprintState,
        nickname="deleteById",
        notes="deletes a blueprint by its id."
    )
    @exceptions_handled
    @marshal_with(responses_v2.BlueprintState)
    def delete(self, blueprint_id, **kwargs):
        """
        Delete blueprint by id
        """
        with resources.skip_nested_marshalling():
            return super(BlueprintsId, self).delete(
                blueprint_id=blueprint_id, **kwargs)


class Executions(resources.Executions):
    @swagger.operation(
        responseClass='List[{0}]'.format(responses_v2.Execution.__name__),
        nickname="list",
        notes='Returns a list of executions for the optionally provided filter'
              ' parameters: {0}'.format(models.Execution.fields),
        parameters=_create_filter_params_list_description(
            models.Execution.fields, 'executions') + [
            {'name': '_include_system_workflows',
             'description': 'Include executions of system workflows',
             'required': False,
             'allowMultiple': True,
             'dataType': 'bool',
             'defaultValue': False,
             'paramType': 'query'}
        ]
    )
    @exceptions_handled
    @marshal_with(responses_v2.Execution)
    @verify_and_create_filters(models.Execution.fields)
    @paginate
    def get(self, _include=None, filters=None, pagination=None, **kwargs):
        """
        List executions
        """
        deployment_id = request.args.get('deployment_id')
        if deployment_id:
            get_blueprints_manager().get_deployment(deployment_id,
                                                    include=['id'])
        is_include_system_workflows = verify_and_convert_bool(
            '_include_system_workflows',
            request.args.get('_include_system_workflows', 'false'))

        executions = get_blueprints_manager().executions_list(
            filters=filters, pagination=pagination,
            is_include_system_workflows=is_include_system_workflows,
            include=_include)
        return executions


class Deployments(resources.Deployments):
    @swagger.operation(
        responseClass='List[{0}]'.format(responses_v2.Deployment.__name__),
        nickname="list",
        notes='Returns a list existing deployments for the optionally provided'
              ' filter parameters: {0}'.format(models.Deployment.fields),
        parameters=_create_filter_params_list_description(
            models.Deployment.fields,
            'deployments'
        )
    )
    @exceptions_handled
    @marshal_with(responses_v2.Deployment)
    @verify_and_create_filters(models.Deployment.fields)
    @paginate
    def get(self, _include=None, filters=None, pagination=None, **kwargs):
        """
        List deployments
        """
        deployments = get_blueprints_manager().deployments_list(
            include=_include, filters=filters, pagination=pagination)
        return deployments


class DeploymentModifications(resources.DeploymentModifications):
    @swagger.operation(
        responseClass='List[{0}]'.format(
            responses_v2.DeploymentModification.__name__),
        nickname="listDeploymentModifications",
        notes='Returns a list of deployment modifications for the optionally '
              'provided filter parameters: {0}'
        .format(models.DeploymentModification.fields),
        parameters=_create_filter_params_list_description(
            models.DeploymentModification.fields,
            'deployment modifications'
        )
    )
    @exceptions_handled
    @marshal_with(responses_v2.DeploymentModification)
    @verify_and_create_filters(models.DeploymentModification.fields)
    @paginate
    def get(self, _include=None, filters=None, pagination=None, **kwargs):
        """
        List deployment modifications
        """
        modifications = get_storage_manager().deployment_modifications_list(
            include=_include, filters=filters, pagination=pagination)
        return modifications


class Nodes(resources.Nodes):
    @swagger.operation(
        responseClass='List[{0}]'.format(responses_v2.Node.__name__),
        nickname="listNodes",
        notes='Returns a nodes list for the optionally provided filter '
              'parameters: {0}'.format(models.DeploymentNode.fields),
        parameters=_create_filter_params_list_description(
            models.DeploymentNode.fields,
            'nodes'
        )
    )
    @exceptions_handled
    @marshal_with(responses_v2.Node)
    @verify_and_create_filters(models.DeploymentNode.fields)
    @paginate
    def get(self, _include=None, filters=None, pagination=None, **kwargs):
        """
        List nodes
        """
        nodes = get_storage_manager().get_nodes(include=_include,
                                                pagination=pagination,
                                                filters=filters)
        return nodes


class NodeInstances(resources.NodeInstances):
    @swagger.operation(
        responseClass='List[{0}]'.format(responses_v2.NodeInstance.__name__),
        nickname="listNodeInstances",
        notes='Returns a node instances list for the optionally provided '
              'filter parameters: {0}'
        .format(models.DeploymentNodeInstance.fields),
        parameters=_create_filter_params_list_description(
            models.DeploymentNodeInstance.fields,
            'node instances'
        )
    )
    @exceptions_handled
    @marshal_with(responses_v2.NodeInstance)
    @verify_and_create_filters(models.DeploymentNodeInstance.fields)
    @paginate
    def get(self, _include=None, filters=None, pagination=None, **kwargs):
        """
        List node instances
        """
        node_instances = get_storage_manager().get_node_instances(
            include=_include, filters=filters, pagination=pagination)
        return node_instances


class ProviderContext(resources.ProviderContext):
    @swagger.operation(
        responseClass=responses_v2.ProviderContext,
        notes="Updates the provider context",
        parameters=[{'name': 'global_parallel_executions_limit',
                     'description': "the global parallel executions limit",
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'int',
                     'paramType': 'body'},
                    ],
        consumes=[
            "application/json"
        ]
    )
    @exceptions_handled
    @marshal_with(responses_v2.ProviderContext)
    def patch(self, **kwargs):
        """
        modifies provider context configuration
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('global_parallel_executions_limit',
                                         request_json)

        provider_ctx = get_storage_manager().get_provider_context()
        bootstrap_ctx = provider_ctx.context.get('cloudify', {})

        transient_dep_workers_mode_enabled = bootstrap_ctx.get(
            'transient_deployment_workers_mode', {}).get(
            'enabled', TRANSIENT_WORKERS_MODE_ENABLED_DEFAULT)
        if not transient_dep_workers_mode_enabled:
            raise manager_exceptions.BadParametersError(
                "can't modify global_parallel_executions_limit since transient"
                ' deployment workers mode is disabled')

        limit = request_json['global_parallel_executions_limit']
        if type(limit) is not int:
            raise manager_exceptions.BadParametersError(
                'global_parallel_executions_limit parameter should be of type'
                ' int, but is instead of type {0}'.format(
                    type(limit).__name__))

        trans_dep_workers_mode = bootstrap_ctx.get(
            'transient_deployment_workers_mode', {})
        trans_dep_workers_mode['global_parallel_executions_limit'] = limit

        bootstrap_ctx['transient_deployment_workers_mode'] = \
            trans_dep_workers_mode
        provider_ctx.context['cloudify'] = bootstrap_ctx
        get_storage_manager().update_provider_context(provider_ctx)
        return get_storage_manager().get_provider_context()


class Plugins(SecuredResource):
    @swagger.operation(
        responseClass='List[{0}]'.format(responses_v2.NodeInstance.__name__),
        nickname="listPlugins",
        notes='Returns a plugins list for the optionally provided '
              'filter parameters: {0}'.format(models.Plugin.fields),
        parameters=_create_filter_params_list_description(
            models.Plugin.fields,
            'plugins'
        )
    )
    @exceptions_handled
    @marshal_with(responses_v2.Plugin)
    @verify_and_create_filters(models.Plugin.fields)
    @paginate
    def get(self, _include=None, filters=None, pagination=None, **kwargs):
        """
        List uploaded plugins
        """
        plugins = get_storage_manager().get_plugins(include=_include,
                                                    filters=filters,
                                                    pagination=pagination)
        return plugins

    @swagger.operation(
        responseClass=responses_v2.Plugin,
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
    @exceptions_handled
    @marshal_with(responses_v2.Plugin)
    def post(self, **kwargs):
        """
        Upload a plugin
        """
        return UploadedPluginsManager().receive_uploaded_data(str(uuid4()))


class UploadedPluginsManager(files.UploadedDataManager):

    def _get_kind(self):
        return 'plugin'

    def _get_data_url_key(self):
        return 'plugin_archive_url'

    def _get_target_dir_path(self):
        return config.instance().file_server_uploaded_plugins_folder

    def _get_archive_type(self, archive_path):
        return 'tar.gz'

    def _prepare_and_process_doc(self, data_id, file_server_root,
                                 archive_target_path):
        new_plugin = self._create_plugin_from_archive(data_id,
                                                      archive_target_path)

        filter_by_name = {'package_name': new_plugin.package_name}
        plugins = get_storage_manager().get_plugins(filters=filter_by_name)

        for plugin in plugins:
            if plugin.archive_name == new_plugin.archive_name:
                raise manager_exceptions.ConflictError(
                    'a plugin archive by the name of {archive_name} already '
                    'exists for package with name {package_name} and version '
                    '{version}'.format(archive_name=new_plugin.archive_name,
                                       package_name=new_plugin.package_name,
                                       version=new_plugin.package_version))
        else:
            get_storage_manager().put_plugin(new_plugin)

        return new_plugin, new_plugin.archive_name

    def _create_plugin_from_archive(self, plugin_id, archive_path):
        plugin = self._load_plugin_package_json(archive_path)
        build_props = plugin.get('build_server_os_properties')
        now = str(datetime.now())
        return models.Plugin(
            id=plugin_id,
            package_name=plugin.get('package_name'),
            package_version=plugin.get('package_version'),
            archive_name=plugin.get('archive_name'),
            package_source=plugin.get('package_source'),
            supported_platform=plugin.get('supported_platform'),
            distribution=build_props.get('distribution'),
            distribution_version=build_props.get('distribution_version'),
            distribution_release=build_props.get('distribution_release'),
            wheels=plugin.get('wheels'),
            excluded_wheels=plugin.get('excluded_wheels'),
            supported_py_versions=plugin.get('supported_python_versions'),
            uploaded_at=now)

    @staticmethod
    def _load_plugin_package_json(tar_source):

        if not tarfile.is_tarfile(tar_source):
            raise manager_exceptions.InvalidPluginError(
                'the provided tar archive can not be read.')

        with tarfile.open(tar_source) as tar:
            tar_members = tar.getmembers()
            # a wheel plugin will contain exactly one sub directory
            if not tar_members:
                raise manager_exceptions.InvalidPluginError(
                    'archive file structure malformed. expecting exactly one '
                    'sub directory; got none.')
            package_json_path = os.path.join(tar_members[0].name,
                                             'package.json')
            try:
                package_member = tar.getmember(package_json_path)
            except KeyError:
                raise manager_exceptions. \
                    InvalidPluginError("'package.json' was not found under {0}"
                                       .format(package_member))
            try:
                package_json = tar.extractfile(package_member)
            except (tarfile.ExtractError, tarfile.EnvironmentError) as e:
                raise manager_exceptions. \
                    InvalidPluginError(str(e))
            try:
                return json.load(package_json)
            except ValueError as e:
                raise manager_exceptions. \
                    InvalidPluginError("'package.json' is not a valid json: "
                                       "{json_str}. error is {error}"
                                       .format(json_str=package_json.read(),
                                               error=str(e)))


class PluginsArchive(SecuredResource):
    """
    GET = download previously uploaded plugin package.
    """
    @swagger.operation(
        responseClass='archive file',
        nickname="downloadPlugin",
        notes="download a plugin archive according to the plugin ID. ",
        )
    @exceptions_handled
    def get(self, plugin_id, **kwargs):
        """
        Download plugin archive
        """
        # Verify plugin exists.
        plugin = get_blueprints_manager().get_plugin(plugin_id)

        archive_name = plugin.archive_name
        # attempting to find the archive file on the file system
        local_path = _get_plugin_archive_path(plugin_id, archive_name)
        if not os.path.isfile(local_path):
            raise RuntimeError("Could not find plugins archive; "
                               "Plugin ID: {0}".format(plugin_id))

        plugin_path = '{0}/{1}/{2}/{3}'.format(
            config.instance().file_server_resources_uri,
            'plugins',
            plugin_id,
            archive_name)

        return make_streaming_response(
            plugin_id,
            plugin_path,
            os.path.getsize(local_path),
            'tar.gz'
        )


class PluginsId(SecuredResource):
    @swagger.operation(
        responseClass=responses_v2.BlueprintState,
        nickname="getById",
        notes="Returns a plugin according to its ID."
    )
    @exceptions_handled
    @marshal_with(responses_v2.Plugin)
    def get(self, plugin_id, _include=None, **kwargs):
        """
        Returns plugin by ID
        """
        return get_storage_manager().get_plugin(plugin_id, include=_include)

    @swagger.operation(
        responseClass=responses_v2.Plugin,
        nickname="deleteById",
        notes="deletes a plugin according to its ID."
    )
    @exceptions_handled
    @marshal_with(responses_v2.Plugin)
    def delete(self, plugin_id, **kwargs):
        """
        Delete plugin by ID
        """
        # Verify plugin exists.
        plugin = get_blueprints_manager().get_plugin(plugin_id)
        archive_name = plugin.archive_name
        archive_path = _get_plugin_archive_path(plugin_id, archive_name)
        shutil.rmtree(os.path.dirname(archive_path), ignore_errors=True)
        get_storage_manager().delete_plugin(plugin_id)
        return plugin


def _get_plugin_archive_path(plugin_id, archive_name):
    return os.path.join(config.instance().file_server_uploaded_plugins_folder,
                        plugin_id,
                        archive_name)

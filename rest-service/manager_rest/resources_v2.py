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
import tempfile
from uuid import uuid4

from datetime import datetime
from collections import OrderedDict

from flask_restful_swagger import swagger
from flask import request
from flask.ext.restful import marshal

from dsl_parser.parser import parse_from_path
from flask_securest.rest_security import SecuredResource

from manager_rest import resources
from manager_rest import utils
from manager_rest.deployment_updates_manager import \
    get_deployment_updates_manager
from manager_rest.resources import (marshal_with,
                                    exceptions_handled,
                                    verify_and_convert_bool,
                                    verify_parameter_in_request_body,
                                    verify_json_content_type,
                                    make_streaming_response,
                                    CONVENTION_APPLICATION_BLUEPRINT_FILE)
from manager_rest import models
from manager_rest import responses_v2
from manager_rest import manager_exceptions
from manager_rest import config
from manager_rest import files
from manager_rest.storage_manager import get_storage_manager
from manager_rest.storage_manager import ListResult
from manager_rest.blueprints_manager import get_blueprints_manager


from manager_rest.manager_elasticsearch import ManagerElasticsearch


def projection(func):
    """Decorator for enabling projection
    """
    def create_projection_params(*args, **kw):
        projection_params = None
        if '_include' in request.args:
            projection_params = request.args["_include"].split(',')
        return func(_include=projection_params, *args, **kw)
    return create_projection_params


def rangeable(func):
    """
    Decorator for enabling range
    """
    def create_range_params(*args, **kw):
        range_args = request.args.getlist("_range")
        range_params = {}
        for range_arg in range_args:
            try:
                range_key, range_from, range_to = \
                    range_arg.split(',')
            except ValueError:
                raise ValueError('Range parameter requires 3 values')
            range_param = {}
            if range_from:
                range_param['from'] = range_from
            if range_to:
                range_param['to'] = range_to
            if range_param:
                range_params[range_key] = range_param

        return func(range_filters=range_params, *args, **kw)
    return create_range_params


def sortable(func):
    """
    Decorator for enabling sort
    """
    def create_sort_params(*args, **kw):
        sort_args = request.args.getlist("_sort")
        # maintain order of sort fields
        sort_params = OrderedDict()
        for sort_arg in sort_args:
            field = sort_arg.lstrip('-+')
            order = "desc" if sort_arg[0] == '-' else "asc"
            sort_params.update({field: order})
        return func(sort=sort_params, *args, **kw)
    return create_sort_params


def marshal_events(func):
    """
    Decorator for marshalling raw event responses
    """
    def marshal_response(*args, **kwargs):
        return marshal(func(*args, **kwargs),
                       responses_v2.ListResponse.resource_fields)
    return marshal_response


def paginate(func):
    """
    Decorator for adding pagination
    """
    def verify_and_create_pagination_params(*args, **kw):
        offset = request.args.get('_offset')
        size = request.args.get('_size')
        pagination_params = {}
        if offset:
            pagination_params['offset'] = int(offset)
        if size:
            pagination_params['size'] = int(size)
        result = func(pagination=pagination_params, *args, **kw)

        return responses_v2.ListResponse(
            items=result.items,
            metadata=result.metadata)

    return verify_and_create_pagination_params


def create_filters(fields=None):
    """
    Decorator for extracting filter parameters from the request arguments and
    optionally verifying their validity according to the provided fields.
    :param fields: a set of valid filter fields.
    :return: a Decorator for creating and validating the accepted fields.
    """
    def create_filters_dec(f):
        def some_func(*args, **kw):
            request_args = request.args.to_dict(flat=False)
            # NOTE: all filters are created as lists
            filters = {k: v for k, v in
                       request_args.iteritems() if not k.startswith('_')}
            if fields:
                unknowns = [k for k in filters.iterkeys() if k not in fields]
                if unknowns:
                    raise manager_exceptions.BadParametersError(
                        'Filter keys \'{key_names}\' do not exist. Allowed '
                        'filters are: {fields}'
                        .format(key_names=unknowns, fields=list(fields)))
            return f(filters=filters, *args, **kw)
        return some_func
    return create_filters_dec


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
    @paginate
    @sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        return get_blueprints_manager().snapshots_list(include=_include,
                                                       filters=filters,
                                                       pagination=pagination,
                                                       sort=sort)


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
        snap = get_blueprints_manager().get_snapshot(snapshot_id)
        if snap.status == models.Snapshot.FAILED:
            raise manager_exceptions.SnapshotActionError(
                'Failed snapshot cannot be downloaded'
            )

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
        force = verify_and_convert_bool('force', request_json['force'])
        execution = get_blueprints_manager().restore_snapshot(
            snapshot_id,
            recreate_deployments_envs,
            force
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
    @create_filters(models.BlueprintState.fields)
    @paginate
    @sortable
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            **kwargs):
        """
        List uploaded blueprints
        """
        return get_blueprints_manager().blueprints_list(
            include=_include, filters=filters,
            pagination=pagination, sort=sort)


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
    @create_filters(models.Execution.fields)
    @paginate
    @sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
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
            filters=filters, pagination=pagination, sort=sort,
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
    @create_filters(models.Deployment.fields)
    @paginate
    @sortable
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            **kwargs):
        """
        List deployments
        """
        deployments = get_blueprints_manager().deployments_list(
            include=_include, filters=filters, pagination=pagination,
            sort=sort)
        return deployments


class DeploymentUpdateSteps(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2.DeploymentUpdateStep)
    def post(self, update_id):
        verify_json_content_type()
        request_json = request.json

        manager = get_deployment_updates_manager()
        update_step = \
            manager.create_deployment_update_step(
                update_id,
                request_json.get('operation'),
                request_json.get('entity_type'),
                request_json.get('entity_id')
            )
        return update_step


class DeploymentUpdates(SecuredResource):
    @swagger.operation(
        responseClass='List[{0}]'.format(
            responses_v2.DeploymentUpdate.__name__),
        nickname="listDeploymentUpdates",
        notes='Returns a list of deployment updates',
        parameters=_create_filter_params_list_description(
            models.DeploymentUpdate.fields,
            'deployment updates'
        )
    )
    @exceptions_handled
    @marshal_with(responses_v2.DeploymentUpdate)
    @create_filters(models.DeploymentUpdate.fields)
    @paginate
    @sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List deployment modification stages
        """
        deployment_updates = \
            get_deployment_updates_manager().deployment_updates_list(
                include=None, filters=None, pagination=None,
                sort=None, **kwargs)
        return deployment_updates

    @swagger.operation(
        responseClass=responses_v2.DeploymentUpdate,
        nickname="uploadDeploymentUpdate",
        notes="Uploads an archive for staging",
        parameters=[{'name': 'deployment_id',
                     'description': 'The deployment id to update',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query'},
                    {'name': 'application_file_name',
                     'description': 'The name of the app blueprint',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'string',
                     'defaultValue': 'blueprint.yaml'},
                    {'name': 'blueprint_archive_url',
                     'description': 'The path of the archive (only if the '
                                    'archive is an online resource',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query'}
                    ]
    )
    @exceptions_handled
    @marshal_with(responses_v2.DeploymentUpdate)
    def post(self, **kwargs):
        query_params = request.args
        main_blueprint_key = 'application_file_name'
        blueprint_archive_url_key = 'blueprint_archive_url'
        deployment_id = query_params['deployment_id']

        blueprint_filename = \
            query_params.get(main_blueprint_key,
                             CONVENTION_APPLICATION_BLUEPRINT_FILE)

        # Downloading the file to the local machine
        temp_dir = tempfile.mkdtemp()
        archive_destination = \
            os.path.join(temp_dir,
                         "{0}-{1}".format(deployment_id, blueprint_filename))

        # Saving the archive locally
        utils.save_request_content_to_file(request, archive_destination,
                                           'blueprint',
                                           blueprint_archive_url_key)

        # Unpacking the archive
        relative_app_dir = \
            utils.extract_blueprint_archive_to_mgr(temp_dir,
                                                   archive_destination)

        # retrieving and parsing the blueprint
        temp_app_path = os.path.join(temp_dir, relative_app_dir,
                                     blueprint_filename)
        blueprint = parse_from_path(temp_app_path)

        # create a staging object
        update = get_deployment_updates_manager().\
            stage_deployment_update(deployment_id, blueprint)
        return update, 201


class DeploymentUpdateCommit(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2.DeploymentUpdate)
    def post(self, update_id):
        manager = get_deployment_updates_manager()
        return manager.commit_deployment_update(update_id)


class DeploymentUpdateFinalizeCommit(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2.DeploymentUpdate)
    def post(self, update_id):
        manager = get_deployment_updates_manager()
        return manager.finalize_update(update_id)


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
    @create_filters(models.DeploymentModification.fields)
    @paginate
    @sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List deployment modifications
        """
        modifications = get_storage_manager().deployment_modifications_list(
            include=_include, filters=filters, pagination=pagination,
            sort=sort)
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
    @create_filters(models.DeploymentNode.fields)
    @paginate
    @sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List nodes
        """
        nodes = get_storage_manager().get_nodes(include=_include,
                                                pagination=pagination,
                                                filters=filters,
                                                sort=sort)
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
    @create_filters(models.DeploymentNodeInstance.fields)
    @paginate
    @sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List node instances
        """
        node_instances = get_storage_manager().get_node_instances(
            include=_include, filters=filters,
            pagination=pagination, sort=sort)
        return node_instances


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
    @create_filters(models.Plugin.fields)
    @paginate
    @sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List uploaded plugins
        """
        plugins = get_storage_manager().get_plugins(include=_include,
                                                    filters=filters,
                                                    pagination=pagination,
                                                    sort=sort)
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
        plugins = get_storage_manager().get_plugins(
            filters=filter_by_name).items

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
        notes="download a plugin archive according to the plugin ID. "
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


class Events(resources.Events):

    @staticmethod
    def _build_query(filters=None, pagination=None, sort=None,
                     range_filters=None):

        ctx_fields = [
            'blueprint_id',
            'deployment_id',
            'execution_id',
            'node_id',
            'node_instance_id',
            'workflow_id'
        ]

        # append 'context.' prefix to context fields in all constructs
        query_constructs = \
            [filters, pagination, sort, range_filters]
        for ctx_field in ctx_fields:
            for construct in query_constructs:
                if construct and ctx_field in construct:
                    construct['context.{0}'.format(ctx_field)] = \
                        construct.pop(ctx_field)

        # TODO: monkey patching a wildcard with a filter, should be refactored
        wildcards = dict()
        if filters and 'message.text' in filters:
            wildcards['message.text'] = filters.pop('message.text')[0]

        return ManagerElasticsearch.\
            build_request_body(filters=filters,
                               pagination=pagination,
                               sort=sort,
                               range_filters=range_filters,
                               wildcards=wildcards)

    @staticmethod
    def list_events(query, include=None):
        result = ManagerElasticsearch.search_events(body=query,
                                                    include=include)
        events = ManagerElasticsearch.extract_search_result_values(result)
        metadata = ManagerElasticsearch.build_list_result_metadata(query,
                                                                   result)
        return ListResult(events, metadata)

    @swagger.operation(
        responseclass='List[Event]',
        nickname="list events",
        notes='Returns a list of events for optionally provided filters'
    )
    @exceptions_handled
    @marshal_events
    @create_filters()
    @paginate
    @rangeable
    @projection
    @sortable
    def get(self, _include=None, filters=None,
            pagination=None, sort=None, range_filters=None, **kwargs):
        """
        List events
        """
        query = self._build_query(filters=filters,
                                  pagination=pagination,
                                  sort=sort,
                                  range_filters=range_filters)
        return self.list_events(query, include=_include)

    @exceptions_handled
    def post(self):
        raise manager_exceptions.MethodNotAllowedError()


def _get_plugin_archive_path(plugin_id, archive_name):
    return os.path.join(config.instance().file_server_uploaded_plugins_folder,
                        plugin_id,
                        archive_name)

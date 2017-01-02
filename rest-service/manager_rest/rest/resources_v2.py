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

import os
import shutil
import sys

from uuid import uuid4

from flask import request
from flask_restful_swagger import swagger
from sqlalchemy import bindparam

from manager_rest import (
    config,
    manager_exceptions,
    utils,
)
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest import (
    resources,
    rest_decorators,
    rest_utils,
)
from manager_rest.security import SecuredResource
from manager_rest.storage.models_base import db
from manager_rest.storage.resource_models import (
    Deployment,
    Event,
    Log,
)
from manager_rest.storage.models_states import SnapshotState
from manager_rest.upload_manager import (
    UploadedPluginsManager,
    UploadedSnapshotsManager,
)
from manager_rest.storage import (
    ListResult,
    get_storage_manager,
    models,
)
from manager_rest.utils import create_filter_params_list_description


def _get_snapshot_path(snapshot_id):
    return os.path.join(
        config.instance.file_server_root,
        config.instance.file_server_snapshots_folder,
        snapshot_id
    )


class Snapshots(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(models.Snapshot.__name__),
        nickname='list',
        notes='Returns a list of existing snapshots.'
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Snapshot)
    @rest_decorators.create_filters(models.Snapshot.resource_fields)
    @rest_decorators.paginate
    @rest_decorators.sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        return get_storage_manager().list(
            models.Snapshot,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )


class SnapshotsId(SecuredResource):

    @swagger.operation(
        responseClass=models.Snapshot,
        nickname='getById',
        notes='Returns a snapshot by its id.'
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Snapshot)
    def get(self, snapshot_id, _include=None, **kwargs):
        return get_storage_manager().get(
            models.Snapshot,
            snapshot_id,
            include=_include
        )

    @swagger.operation(
        responseClass=models.Snapshot,
        nickname='createSnapshot',
        notes='Create a new snapshot of the manager.',
        consumes=[
            "application/json"
        ]
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Execution)
    def put(self, snapshot_id):
        request_dict = rest_utils.get_json_and_verify_params()
        include_metrics = rest_utils.verify_and_convert_bool(
            'include_metrics',
            request_dict.get('include_metrics', 'false')
        )
        include_credentials = rest_utils.verify_and_convert_bool(
            'include_credentials',
            request_dict.get('include_credentials', 'true')
        )
        private_resource = rest_utils.verify_and_convert_bool(
            'private_resource',
            request_dict.get('private_resource', 'false')
        )
        bypass_maintenance = is_bypass_maintenance_mode()

        execution = get_resource_manager().create_snapshot(
            snapshot_id,
            include_metrics,
            include_credentials,
            bypass_maintenance,
            private_resource=private_resource
        )
        return execution, 201

    @swagger.operation(
        responseClass=models.Snapshot,
        nickname='deleteSnapshot',
        notes='Delete existing snapshot.'
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Snapshot)
    def delete(self, snapshot_id):
        sm = get_storage_manager()
        snapshot = sm.get(models.Snapshot, snapshot_id)
        get_resource_manager().assert_user_has_modify_permissions(snapshot)
        sm.delete(snapshot)
        path = _get_snapshot_path(snapshot_id)
        shutil.rmtree(path, ignore_errors=True)
        return snapshot, 200

    @rest_decorators.exceptions_handled
    def patch(self, snapshot_id):
        """Update snapshot status by id
        """
        request_dict = rest_utils.get_json_and_verify_params({'status'})
        snapshot = get_storage_manager().get(models.Snapshot, snapshot_id)
        get_resource_manager().assert_user_has_modify_permissions(snapshot)

        snapshot.status = request_dict['status']
        snapshot.error = request_dict.get('error', '')
        get_storage_manager().update(snapshot)


class SnapshotsIdArchive(SecuredResource):

    @swagger.operation(
        responseClass=models.Snapshot,
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
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Snapshot)
    def put(self, snapshot_id):
        return UploadedSnapshotsManager().receive_uploaded_data(snapshot_id)

    @swagger.operation(
        nickname='downloadSnapshot',
        notes='Downloads snapshot as an archive.'
    )
    @rest_decorators.exceptions_handled
    def get(self, snapshot_id):
        snap = get_storage_manager().get(models.Snapshot, snapshot_id)
        if snap.status == SnapshotState.FAILED:
            raise manager_exceptions.SnapshotActionError(
                'Failed snapshot cannot be downloaded'
            )

        snapshot_path = os.path.join(
            _get_snapshot_path(snapshot_id),
            '{0}.zip'.format(snapshot_id)
        )

        snapshot_uri = '{0}/{1}/{2}/{2}.zip'.format(
            config.instance.file_server_resources_uri,
            config.instance.file_server_snapshots_folder,
            snapshot_id
        )

        return rest_utils.make_streaming_response(
            snapshot_id,
            snapshot_uri,
            os.path.getsize(snapshot_path),
            'zip'
        )


class SnapshotsIdRestore(SecuredResource):
    @swagger.operation(
        responseClass=models.Snapshot,
        nickname='restoreSnapshot',
        notes='Restore existing snapshot.'
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Snapshot)
    def post(self, snapshot_id):
        request_dict = rest_utils.get_json_and_verify_params(
            {'recreate_deployments_envs', 'tenant_name'}
        )
        recreate_deployments_envs = rest_utils.verify_and_convert_bool(
            'recreate_deployments_envs',
            request_dict['recreate_deployments_envs']
        )
        bypass_maintenance = is_bypass_maintenance_mode()
        force = rest_utils.verify_and_convert_bool(
            'force',
            request_dict['force']
        )
        tenant_name = request_dict['tenant_name']
        default_timeout_sec = 300
        request_timeout = request_dict.get('timeout', default_timeout_sec)
        timeout = rest_utils.convert_to_int(request_timeout)
        execution = get_resource_manager().restore_snapshot(
            snapshot_id,
            recreate_deployments_envs,
            force,
            bypass_maintenance,
            timeout,
            tenant_name
        )
        return execution, 200


class Blueprints(resources.Blueprints):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.Blueprint.__name__),
        nickname="list",
        notes='Returns a list of submitted blueprints for the optionally '
              'provided filter parameters {0}'
        .format(models.Blueprint.resource_fields),
        parameters=create_filter_params_list_description(
            models.Blueprint.resource_fields,
            'blueprints'
        )
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Blueprint)
    @rest_decorators.create_filters(models.Blueprint.resource_fields)
    @rest_decorators.paginate
    @rest_decorators.sortable
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            **kwargs):
        """
        List uploaded blueprints
        """
        return get_storage_manager().list(
            models.Blueprint,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )


class BlueprintsId(resources.BlueprintsId):

    @swagger.operation(
        responseClass=models.Blueprint,
        nickname="getById",
        notes="Returns a blueprint by its id."
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Blueprint)
    def get(self, blueprint_id, _include=None, **kwargs):
        """
        Get blueprint by id
        """
        with rest_utils.skip_nested_marshalling():
            return super(BlueprintsId, self).get(blueprint_id=blueprint_id,
                                                 _include=_include,
                                                 **kwargs)

    @swagger.operation(
        responseClass=models.Blueprint,
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
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Blueprint)
    def put(self, blueprint_id, **kwargs):
        """
        Upload a blueprint (id specified)
        """
        with rest_utils.skip_nested_marshalling():
            return super(BlueprintsId, self).put(blueprint_id=blueprint_id,
                                                 **kwargs)

    @swagger.operation(
        responseClass=models.Blueprint,
        nickname="deleteById",
        notes="deletes a blueprint by its id."
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Blueprint)
    def delete(self, blueprint_id, **kwargs):
        """
        Delete blueprint by id
        """
        with rest_utils.skip_nested_marshalling():
            return super(BlueprintsId, self).delete(
                blueprint_id=blueprint_id, **kwargs)


class Executions(resources.Executions):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.Execution.__name__),
        nickname="list",
        notes='Returns a list of executions for the optionally provided filter'
              ' parameters: {0}'.format(models.Execution.resource_fields),
        parameters=create_filter_params_list_description(
            models.Execution.resource_fields, 'executions') + [
            {'name': '_include_system_workflows',
             'description': 'Include executions of system workflows',
             'required': False,
             'allowMultiple': True,
             'dataType': 'bool',
             'defaultValue': False,
             'paramType': 'query'}
        ]
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Execution)
    @rest_decorators.create_filters(models.Execution.resource_fields)
    @rest_decorators.paginate
    @rest_decorators.sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List executions
        """
        deployment_id = request.args.get('deployment_id')
        if deployment_id:
            get_storage_manager().get(
                models.Deployment,
                deployment_id,
                include=['id']
            )
        is_include_system_workflows = rest_utils.verify_and_convert_bool(
            '_include_system_workflows',
            request.args.get('_include_system_workflows', 'false'))

        return get_resource_manager().list_executions(
            filters=filters,
            pagination=pagination,
            sort=sort,
            is_include_system_workflows=is_include_system_workflows,
            include=_include
        )


class Deployments(resources.Deployments):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.Deployment.__name__),
        nickname="list",
        notes='Returns a list existing deployments for the optionally provided'
              ' filter parameters: '
              '{0}'.format(models.Deployment.resource_fields),
        parameters=create_filter_params_list_description(
            models.Deployment.resource_fields,
            'deployments'
        )
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Deployment)
    @rest_decorators.create_filters(models.Deployment.resource_fields)
    @rest_decorators.paginate
    @rest_decorators.sortable
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            **kwargs):
        """
        List deployments
        """
        return get_storage_manager().list(
            models.Deployment,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )


class DeploymentModifications(resources.DeploymentModifications):
    @swagger.operation(
        responseClass='List[{0}]'.format(
            models.DeploymentModification.__name__),
        nickname="listDeploymentModifications",
        notes='Returns a list of deployment modifications for the optionally '
              'provided filter parameters: {0}'
        .format(models.DeploymentModification.resource_fields),
        parameters=create_filter_params_list_description(
            models.DeploymentModification.resource_fields,
            'deployment modifications'
        )
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.DeploymentModification)
    @rest_decorators.create_filters(
        models.DeploymentModification.resource_fields)
    @rest_decorators.paginate
    @rest_decorators.sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List deployment modifications
        """
        return get_storage_manager().list(
            models.DeploymentModification,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )


class Nodes(resources.Nodes):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.Node.__name__),
        nickname="listNodes",
        notes='Returns a nodes list for the optionally provided filter '
              'parameters: {0}'.format(models.Node.resource_fields),
        parameters=create_filter_params_list_description(
            models.Node.resource_fields,
            'nodes'
        )
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Node)
    @rest_decorators.create_filters(models.Node.resource_fields)
    @rest_decorators.paginate
    @rest_decorators.sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List nodes
        """
        return get_storage_manager().list(
            models.Node,
            include=_include,
            pagination=pagination,
            filters=filters,
            sort=sort
        )


class NodeInstances(resources.NodeInstances):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.NodeInstance.__name__),
        nickname="listNodeInstances",
        notes='Returns a node instances list for the optionally provided '
              'filter parameters: {0}'
        .format(models.NodeInstance.resource_fields),
        parameters=create_filter_params_list_description(
            models.NodeInstance.resource_fields,
            'node instances'
        )
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.NodeInstance)
    @rest_decorators.create_filters(models.NodeInstance.resource_fields)
    @rest_decorators.paginate
    @rest_decorators.sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List node instances
        """
        return get_storage_manager().list(
            models.NodeInstance,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )


class Plugins(SecuredResource):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.NodeInstance.__name__),
        nickname="listPlugins",
        notes='Returns a plugins list for the optionally provided '
              'filter parameters: {0}'.format(models.Plugin.resource_fields),
        parameters=create_filter_params_list_description(
            models.Plugin.resource_fields,
            'plugins'
        )
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Plugin)
    @rest_decorators.create_filters(models.Plugin.resource_fields)
    @rest_decorators.paginate
    @rest_decorators.sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List uploaded plugins
        """
        return get_storage_manager().list(
            models.Plugin,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort
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
    @rest_decorators.marshal_with(models.Plugin)
    def post(self, **kwargs):
        """
        Upload a plugin
        """
        plugin, code = UploadedPluginsManager().receive_uploaded_data(
            str(uuid4()))
        try:
            get_resource_manager().install_plugin(plugin)
        except manager_exceptions.ExecutionTimeout:
            tp, ex, tb = sys.exc_info()
            raise manager_exceptions.PluginInstallationTimeout(
                'Timed out during plugin installation. ({0}: {1})'
                .format(tp.__name__, ex)), None, tb
        except Exception:
            get_resource_manager().remove_plugin(
                plugin_id=plugin.id, force=True)
            tp, ex, tb = sys.exc_info()
            raise manager_exceptions.PluginInstallationError(
                'Failed during plugin installation. ({0}: {1})'
                .format(tp.__name__, ex)), None, tb
        return plugin, code


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
    def get(self, plugin_id, **kwargs):
        """
        Download plugin archive
        """
        # Verify plugin exists.
        plugin = get_storage_manager().get(models.Plugin, plugin_id)

        archive_name = plugin.archive_name
        # attempting to find the archive file on the file system
        local_path = utils.get_plugin_archive_path(plugin_id, archive_name)
        if not os.path.isfile(local_path):
            raise RuntimeError("Could not find plugins archive; "
                               "Plugin ID: {0}".format(plugin_id))

        plugin_path = '{0}/{1}/{2}/{3}'.format(
            config.instance.file_server_resources_uri,
            'plugins',
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
    @rest_decorators.marshal_with(models.Plugin)
    def delete(self, plugin_id, **kwargs):
        """
        Delete plugin by ID
        """
        return get_resource_manager().remove_plugin(plugin_id=plugin_id,
                                                    force=False)


class Events(resources.Events):

    """Events resource.

    Through the events endpoint a user can retrieve both events and logs as
    stored in the SQL database.

    """

    @swagger.operation(
        responseclass='List[Event]',
        nickname="list events",
        notes='Returns a list of events for optionally provided filters'
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_events
    @rest_decorators.create_filters()
    @rest_decorators.paginate
    @rest_decorators.rangeable
    @rest_decorators.projection
    @rest_decorators.sortable
    def get(self, _include=None, filters=None,
            pagination=None, sort=None, range_filters=None, **kwargs):
        """List events using a SQL backend.

        :param _include:
            Projection used to get records from database (not currently used)
        :type _include: list(str)
        :param filters:
            Filter selection.

            It's used to decide if events:
                {'type': ['cloudify_event']}
            or both events and logs should be returned:
                {'type': ['cloudify_event', 'cloudify_log']}

            Also it's used to get only events for a particular execution:
                {'execution_id': '<some uuid>'}
        :type filters: dict(str, str)
        :param pagination:
            Parameters used to limit results returned in a single query.
            Expected values `size` and `offset` are mapped into SQL as `LIMIT`
            and `OFFSET`.
        :type pagination: dict(str, int)
        :param sort:
            Result sorting order. The only allowed and expected value is to
            sort by timestamp in ascending order:
                {'timestamp': 'asc'}
        :type sort: dict(str, str)
        :returns: Events that match the conditions passed as arguments
        :rtype: :class:`manager_rest.storage.storage_manager.ListResult`
        :param range_filters:
            Apparently was used to select a timestamp interval. It's not
            currently used.
        :type range_filters: dict(str)
        :returns: Events found in the SQL backend
        :rtype: :class:`manager_rest.storage.storage_manager.ListResult`

        """
        params = {
            'execution_id': filters['execution_id'][0],
            'limit': pagination['size'],
            'offset': pagination['offset'],
        }

        count_query = self._build_count_query(filters)
        total = count_query.params(**params).scalar()

        select_query = self._build_select_query(
            _include, filters, pagination, sort)

        results = [
            self._map_event_to_es(event)
            for event in select_query.params(**params).all()
        ]

        metadata = {
            'pagination': dict(pagination, total=total)
        }
        return ListResult(results, metadata)

    @rest_decorators.exceptions_handled
    def post(self):
        raise manager_exceptions.MethodNotAllowedError()

    @swagger.operation(
        responseclass='List[Event]',
        nickname="delete events",
        notes='Deletes events according to a passed Deployment ID'
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_events
    @rest_decorators.create_filters()
    @rest_decorators.paginate
    @rest_decorators.rangeable
    @rest_decorators.projection
    @rest_decorators.sortable
    def delete(self, filters=None, pagination=None, sort=None,
               range_filters=None, **kwargs):
        """Delete events/logs connected to a certain Deployment ID."""
        if not isinstance(filters, dict) or 'type' not in filters:
            raise manager_exceptions.BadParametersError(
                'Filter by type is expected')

        if 'cloudify_event' not in filters['type']:
            raise manager_exceptions.BadParametersError(
                'At least `type=cloudify_event` filter is expected')

        deployment_query = (
            db.session.query(Deployment.storage_id)
            .filter(Deployment.id == bindparam('deployment_id'))
        )
        params = {
            'deployment_id': filters['deployment_id'][0],
        }

        event_query = (
            db.session.query(Event)
            .filter(Event.deployment_fk == deployment_query.as_scalar())
        )
        total = event_query.params(**params).count()
        event_query.params(**params).delete('fetch')

        if 'cloudify_log' in filters['type']:
            log_query = (
                db.session.query(Log)
                .filter(Log.deployment_fk == deployment_query.as_scalar())
            )
            total += log_query.params(**params).count()
            log_query.params(**params).delete('fetch')

        metadata = {
            'pagination': dict(pagination, total=total)
        }

        # We don't really want to return all of the deleted events, so it's a
        # bit of a hack to return an empty list
        return ListResult([], metadata)

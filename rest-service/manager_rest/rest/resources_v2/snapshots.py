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
import shutil

from flask_restful_swagger import swagger

from cloudify.models_states import SnapshotState

from manager_rest.security import SecuredResource
from manager_rest import config, manager_exceptions
from manager_rest.security.authorization import authorize
from manager_rest.rest import rest_decorators, rest_utils
from manager_rest.storage import get_storage_manager, models
from manager_rest.resource_manager import get_resource_manager
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.upload_manager import UploadedSnapshotsManager
from manager_rest.constants import (FILE_SERVER_SNAPSHOTS_FOLDER,
                                    FILE_SERVER_RESOURCES_FOLDER)

try:
    from cloudify_premium.ha import cluster_status, node_status
except ImportError:
    cluster_status, node_status = None, None


def _get_snapshot_path(snapshot_id):
    return os.path.join(
        config.instance.file_server_root,
        FILE_SERVER_SNAPSHOTS_FOLDER,
        snapshot_id
    )


def _verify_no_multi_node_cluster(action):
    if not (cluster_status and node_status and 'initialized' in node_status):
        return
    if not node_status['initialized']:
        raise manager_exceptions.IllegalActionError(
            'Action `{0}` is not available while '
            'initializing a cluster'.format(action)
        )
    if len(cluster_status.nodes) > 1:
        raise manager_exceptions.IllegalActionError(
            'Action `{0}` is not available on a '
            'cluster with more than one node'.format(action)
        )


class Snapshots(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(models.Snapshot.__name__),
        nickname='list',
        notes='Returns a list of existing snapshots.'
    )
    @rest_decorators.exceptions_handled
    @authorize('snapshot_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Snapshot)
    @rest_decorators.create_filters(models.Snapshot)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Snapshot)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, all_tenants=None, search=None, **kwargs):
        return get_storage_manager().list(
            models.Snapshot,
            include=_include,
            filters=filters,
            substr_filters=search,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants
        )


class SnapshotsId(SecuredResource):

    @swagger.operation(
        responseClass=models.Snapshot,
        nickname='getById',
        notes='Returns a snapshot by its id.'
    )
    @rest_decorators.exceptions_handled
    @authorize('snapshot_get')
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
    @authorize('snapshot_create')
    @rest_decorators.marshal_with(models.Execution)
    def put(self, snapshot_id):
        rest_utils.validate_inputs({'snapshot_id': snapshot_id})
        request_dict = rest_utils.get_json_and_verify_params()
        include_metrics = rest_utils.verify_and_convert_bool(
            'include_metrics',
            request_dict.get('include_metrics', 'false')
        )
        include_credentials = rest_utils.verify_and_convert_bool(
            'include_credentials',
            request_dict.get('include_credentials', 'true')
        )
        include_logs = rest_utils.verify_and_convert_bool(
            'include_logs',
            request_dict.get('include_logs', 'true')
        )
        include_events = rest_utils.verify_and_convert_bool(
            'include_events',
            request_dict.get('include_events', 'true')
        )
        queue = rest_utils.verify_and_convert_bool(
            'queue',
            request_dict.get('queue', 'false')
        )
        execution = get_resource_manager().create_snapshot(
            snapshot_id,
            include_metrics,
            include_credentials,
            include_logs,
            include_events,
            True,
            queue
        )

        return execution, 201

    @swagger.operation(
        responseClass=models.Snapshot,
        nickname='deleteSnapshot',
        notes='Delete existing snapshot.'
    )
    @rest_decorators.exceptions_handled
    @authorize('snapshot_delete')
    @rest_decorators.marshal_with(models.Snapshot)
    def delete(self, snapshot_id):
        sm = get_storage_manager()
        snapshot = sm.get(models.Snapshot, snapshot_id)
        sm.delete(snapshot)
        path = _get_snapshot_path(snapshot_id)
        shutil.rmtree(path, ignore_errors=True)
        return snapshot, 200

    @rest_decorators.exceptions_handled
    @authorize('snapshot_status_update')
    def patch(self, snapshot_id):
        """Update snapshot status by id
        """
        request_dict = rest_utils.get_json_and_verify_params({'status'})
        snapshot = get_storage_manager().get(models.Snapshot, snapshot_id)

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
    @authorize('snapshot_upload')
    @rest_decorators.marshal_with(models.Snapshot)
    def put(self, snapshot_id):
        return UploadedSnapshotsManager().receive_uploaded_data(snapshot_id)

    @swagger.operation(
        nickname='downloadSnapshot',
        notes='Downloads snapshot as an archive.'
    )
    @rest_decorators.exceptions_handled
    @authorize('snapshot_download')
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
            FILE_SERVER_RESOURCES_FOLDER,
            FILE_SERVER_SNAPSHOTS_FOLDER,
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
    @authorize('snapshot_restore')
    @rest_decorators.marshal_with(models.Snapshot)
    def post(self, snapshot_id):
        _verify_no_multi_node_cluster(action="restore snapshot")
        request_dict = rest_utils.get_json_and_verify_params(
            {'recreate_deployments_envs'}
        )
        recreate_deployments_envs = rest_utils.verify_and_convert_bool(
            'recreate_deployments_envs',
            request_dict['recreate_deployments_envs']
        )
        force = rest_utils.verify_and_convert_bool(
            'force',
            request_dict['force']
        )
        restore_certificates = rest_utils.verify_and_convert_bool(
            'restore_certificates',
            request_dict.get('restore_certificates', 'false')
        )
        no_reboot = rest_utils.verify_and_convert_bool(
            'no_reboot',
            request_dict.get('no_reboot', 'false')
        )
        ignore_plugin_failure = \
            rest_utils.verify_and_convert_bool(
                'ignore_plugin_failure',
                request_dict.get('ignore_plugin_failure', 'false')
            )
        if no_reboot and not restore_certificates:
            raise manager_exceptions.BadParametersError(
                '`no_reboot` is only relevant when `restore_certificates` is '
                'activated')
        default_timeout_sec = 300
        request_timeout = request_dict.get('timeout', default_timeout_sec)
        timeout = rest_utils.convert_to_int(request_timeout)
        execution = get_resource_manager().restore_snapshot(
            snapshot_id,
            recreate_deployments_envs,
            force,
            True,
            timeout,
            restore_certificates,
            no_reboot,
            ignore_plugin_failure
        )
        return execution, 200

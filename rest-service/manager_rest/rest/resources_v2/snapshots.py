#########
# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
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

import pydantic
from flask import request
from typing import Optional

from cloudify.models_states import SnapshotState, ExecutionState

from manager_rest import config, manager_exceptions, workflow_executor
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.rest import rest_decorators, rest_utils, swagger
from manager_rest.persistent_storage import get_storage_handler
from manager_rest.storage import get_storage_manager, models
from manager_rest.resource_manager import get_resource_manager
from manager_rest.upload_manager import upload_snapshot
from manager_rest.constants import FILE_SERVER_SNAPSHOTS_FOLDER


def _get_snapshot_path(snapshot_id):
    return os.path.join(
        config.instance.file_server_root,
        FILE_SERVER_SNAPSHOTS_FOLDER,
        snapshot_id
    )


class Snapshots(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(models.Snapshot.__name__),
        nickname='list',
        notes='Returns a list of existing snapshots.'
    )
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


class _SnapshotCreateArgs(pydantic.BaseModel):
    include_credentials: Optional[bool] = True
    include_logs: Optional[bool] = True
    include_events: Optional[bool] = True
    queue: Optional[bool] = False
    tempdir_path: Optional[str] = None


class _SnapshotStatusUpdateArgs(pydantic.BaseModel):
    status: str
    error: Optional[str] = ''


class SnapshotsId(SecuredResource):

    @swagger.operation(
        responseClass=models.Snapshot,
        nickname='getById',
        notes='Returns a snapshot by its id.'
    )
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
    @authorize('snapshot_create')
    @rest_decorators.marshal_with(models.Execution)
    def put(self, snapshot_id):
        rest_utils.validate_inputs({'snapshot_id': snapshot_id})
        args = _SnapshotCreateArgs.parse_obj(request.json)
        tempdir_path = args.tempdir_path
        if tempdir_path and not os.access(tempdir_path, os.W_OK):
            raise manager_exceptions.ForbiddenError(
                f'Temp dir cannot be created inside unwriteable location '
                f'{tempdir_path}'
            )

        execution, messages = get_resource_manager().create_snapshot(
            snapshot_id,
            args.include_credentials,
            args.include_logs,
            args.include_events,
            True,
            args.queue,
            tempdir_path,
        )
        workflow_executor.execute_workflow(messages)
        return execution, 201

    @swagger.operation(
        responseClass=models.Snapshot,
        nickname='deleteSnapshot',
        notes='Delete existing snapshot.'
    )
    @authorize('snapshot_delete')
    @rest_decorators.marshal_with(models.Snapshot)
    def delete(self, snapshot_id):
        sm = get_storage_manager()
        snapshot = sm.get(models.Snapshot, snapshot_id)
        ongoing_snapshot_execs = sm.list(
            models.Execution,
            get_all_results=True,
            filters={
                'workflow_id': ['create_snapshot', 'restore_snapshot'],
                'status': ExecutionState.ACTIVE_STATES,
            })
        for execution in ongoing_snapshot_execs:
            if execution.parameters.get('snapshot_id') == snapshot_id:
                raise manager_exceptions.SnapshotActionError(
                    f'Cannot delete snapshot `{snapshot_id}` which has an '
                    f'active `{execution.workflow_id}` execution')

        sm.delete(snapshot)
        path = _get_snapshot_path(snapshot_id)
        shutil.rmtree(path, ignore_errors=True)
        return snapshot, 200

    @authorize('snapshot_status_update')
    def patch(self, snapshot_id):
        """Update snapshot status by id
        """
        args = _SnapshotStatusUpdateArgs.parse_obj(request.json)
        snapshot = get_storage_manager().get(models.Snapshot, snapshot_id)

        snapshot.status = args.status
        snapshot.error = args.error
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
    @authorize('snapshot_upload')
    @rest_decorators.marshal_with(models.Snapshot)
    def put(self, snapshot_id):
        upload_snapshot(snapshot_id)
        return get_resource_manager().create_snapshot_model(
            snapshot_id,
            status=SnapshotState.UPLOADED,
        ), 201

    @swagger.operation(
        nickname='downloadSnapshot',
        notes='Downloads snapshot as an archive.'
    )
    @authorize('snapshot_download')
    def get(self, snapshot_id):
        snap = get_storage_manager().get(models.Snapshot, snapshot_id)
        if snap.status == SnapshotState.FAILED:
            raise manager_exceptions.SnapshotActionError(
                'Failed snapshot cannot be downloaded'
            )

        snapshot_uri = f'{FILE_SERVER_SNAPSHOTS_FOLDER}/{snapshot_id}/'\
                       f'{snapshot_id}.zip'

        return get_storage_handler().proxy(snapshot_uri)


class _SnapshotRestoreArgs(pydantic.BaseModel):
    force: Optional[bool] = False
    restore_certificates: Optional[bool] = False
    no_reboot: Optional[bool] = False
    timeout: Optional[int] = 300


class SnapshotsIdRestore(SecuredResource):

    @swagger.operation(
        responseClass=models.Snapshot,
        nickname='restoreSnapshot',
        notes='Restore existing snapshot.'
    )
    @authorize('snapshot_restore')
    @rest_decorators.marshal_with(models.Snapshot)
    def post(self, snapshot_id):
        args = _SnapshotCreateArgs.parse_obj(request.json)
        if args.no_reboot and not args.restore_certificates:
            raise manager_exceptions.BadParametersError(
                '`no_reboot` is only relevant when `restore_certificates` is '
                'activated')
        request_timeout = args.timeout
        timeout = rest_utils.convert_to_int(request_timeout)
        execution, messages = get_resource_manager().restore_snapshot(
            snapshot_id,
            args.force,
            True,
            timeout,
            args.restore_certificates,
            args.no_reboot,
        )
        workflow_executor.execute_workflow(messages)
        return execution, 200

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

from manager_rest import (
    config,
    manager_exceptions,
)
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest import (
    rest_decorators,
    rest_utils,
)
from manager_rest.security import SecuredResource
from manager_rest.storage import (
    get_storage_manager,
    models,
)
from manager_rest.storage.models_states import SnapshotState
from manager_rest.upload_manager import UploadedSnapshotsManager
from manager_rest.constants import (FILE_SERVER_SNAPSHOTS_FOLDER,
                                    FILE_SERVER_RESOURCES_FOLDER)


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
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Snapshot)
    @rest_decorators.create_filters(models.Snapshot)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Snapshot)
    @rest_decorators.all_tenants
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, all_tenants=None, **kwargs):
        return get_storage_manager().list(
            models.Snapshot,
            include=_include,
            filters=filters,
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

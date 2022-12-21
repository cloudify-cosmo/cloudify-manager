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
#

import os
import traceback

from cloudify.models_states import BlueprintUploadState

from manager_rest import (
    config,
    manager_exceptions,
    workflow_executor,
)
from manager_rest.persistent_storage import get_storage_handler
from manager_rest.rest import swagger
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.resource_manager import get_resource_manager
from manager_rest.storage import (get_storage_manager,
                                  models)
from manager_rest.upload_manager import (
    cleanup_blueprint_archive_from_file_server,
    upload_blueprint_archive_to_file_server,
)
from manager_rest.utils import current_tenant
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.rest.rest_utils import validate_inputs
from manager_rest.constants import (SUPPORTED_ARCHIVE_TYPES,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER)


class BlueprintsIdArchive(SecuredResource):

    @swagger.operation(
        nickname="getArchive",
        notes="Downloads blueprint as an archive."
    )
    @authorize('blueprint_download')
    def get(self, blueprint_id, **kwargs):
        """
        Download blueprint's archive
        """
        blueprint = get_storage_manager().get(models.Blueprint, blueprint_id)
        path = os.path.join(
            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
            blueprint.tenant.name,
            blueprint.id,
        )
        archive_type = None
        for archive_file_name in get_storage_handler().list(path):
            for arc_type in SUPPORTED_ARCHIVE_TYPES:
                if archive_file_name.endswith(f'{blueprint.id}.{arc_type}'):
                    archive_type = arc_type
                    break
            if archive_type:
                break
        else:
            raise manager_exceptions.NotFoundError(
                'Could not find blueprint\'s archive; '
                f'Blueprint ID: {blueprint.id}')

        blueprint_path = f'{path}/{blueprint.id}.{archive_type}'
        return get_storage_handler().proxy(blueprint_path)


class Blueprints(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(models.Blueprint.__name__),
        nickname="list",
        notes="Returns a list of uploaded blueprints."
    )
    @authorize('blueprint_list')
    @marshal_with(models.Blueprint)
    def get(self, _include=None, **kwargs):
        """
        List uploaded blueprints
        """

        return get_storage_manager().list(
            models.Blueprint, include=_include).items


class BlueprintsId(SecuredResource):

    @swagger.operation(
        responseClass=models.Blueprint,
        nickname="getById",
        notes="Returns a blueprint by its id."
    )
    @authorize('blueprint_get')
    @marshal_with(models.Blueprint)
    def get(self, blueprint_id, _include=None, **kwargs):
        """
        Get blueprint by id
        """
        return get_storage_manager().get(
            models.Blueprint,
            blueprint_id,
            _include
        )

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
    @authorize('blueprint_upload')
    @marshal_with(models.Blueprint)
    def put(self, blueprint_id, **kwargs):
        """Upload a blueprint (id specified)"""
        rm = get_resource_manager()
        sm = get_storage_manager()

        validate_inputs({'blueprint_id': blueprint_id})

        rm = get_resource_manager()

        with sm.transaction():
            blueprint = models.Blueprint(
                plan=None,
                id=blueprint_id,
                description=None,
                main_file_name='',
                state=BlueprintUploadState.UPLOADING,
            )
            sm.put(blueprint)
            blueprint.upload_execution, messages = rm.upload_blueprint(
                blueprint_id,
                '',
                None,
                config.instance.file_server_root,     # for the import resolver
                config.instance.marketplace_api_url,  # for the import resolver
                labels=None,
            )
            sm.update(blueprint)

        try:
            upload_blueprint_archive_to_file_server(
                blueprint_id)
            workflow_executor.execute_workflow(messages)
        except manager_exceptions.ExistingRunningExecutionError as e:
            blueprint.state = BlueprintUploadState.FAILED_UPLOADING
            blueprint.error = str(e)
            blueprint.error_traceback = traceback.format_exc()
            sm.update(blueprint)
            cleanup_blueprint_archive_from_file_server(
                blueprint_id, current_tenant.name)
            raise
        return blueprint, 201

    @swagger.operation(
        responseClass=models.Blueprint,
        nickname="deleteById",
        notes="deletes a blueprint by its id."
    )
    @authorize('blueprint_delete')
    def delete(self, blueprint_id, **kwargs):
        """
        Delete blueprint by id
        """
        # Note: The current delete semantics are such that if a deployment
        # for the blueprint exists, the deletion operation will fail.
        # However, there is no handling of possible concurrency issue with
        # regard to that matter at the moment.
        get_resource_manager().delete_blueprint(blueprint_id, force=False)
        return None, 204

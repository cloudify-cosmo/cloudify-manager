import json
import traceback
from datetime import datetime
from os.path import join
from urllib.parse import quote as unquote
import pydantic
from typing import Any, Dict, List, Optional

from flask import request

from cloudify.models_states import VisibilityState, BlueprintUploadState

from dsl_parser import constants

from manager_rest.security import SecuredResource
from manager_rest.security.authorization import (
    authorize,
    check_user_action_allowed,
)
from manager_rest.resource_manager import get_resource_manager
from manager_rest import upload_manager, workflow_executor
from manager_rest.rest import (
    rest_utils,
    resources_v1,
    resources_v2,
    rest_decorators,
    swagger,
)
from manager_rest.storage import models, get_storage_manager
from manager_rest.rest.rest_utils import (get_labels_from_plan,
                                          get_labels_list)
from manager_rest.rest.responses import Label
from manager_rest.utils import get_formatted_timestamp, remove, current_tenant
from manager_rest.manager_exceptions import (ConflictError,
                                             IllegalActionError,
                                             BadParametersError,
                                             ImportedBlueprintNotFound)
from manager_rest import config
from manager_rest.constants import FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER


class BlueprintsSetVisibility(SecuredResource):

    @authorize('resource_set_visibility')
    @rest_decorators.marshal_with(models.Blueprint)
    def patch(self, blueprint_id):
        """
        Set the blueprint's visibility
        """
        args = rest_utils.SetVisibilityArgs.parse_obj(request.json)
        blueprint = get_storage_manager().get(models.Blueprint, blueprint_id)
        return get_resource_manager().set_visibility(
            blueprint, args.visibility)


class BlueprintsIcon(SecuredResource):
    @authorize('blueprint_upload')
    @rest_decorators.marshal_with(models.Blueprint)
    def patch(self, blueprint_id):
        """
        Set the blueprint's icon
        """
        # Get the blueprint to verify if it exists (in the current context)
        blueprint = get_storage_manager().get(models.Blueprint, blueprint_id)
        if request.data:
            upload_manager.update_blueprint_icon_file(
                blueprint.tenant_name, blueprint_id)
        else:
            upload_manager.remove_blueprint_icon_file(
                blueprint.tenant_name, blueprint_id)
        return blueprint


class _BlueprintUpdateArgs(pydantic.BaseModel):
    class Config:
        extra = 'forbid'

    plan: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    main_file_name: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    labels: Optional[List[Any]] = None
    creator: Optional[str] = None
    created_at: Optional[str] = None
    upload_execution: Optional[str] = None
    visibility: Optional[VisibilityState] = None
    requirements: Optional[dict] = None


class _BlueprintUpdateQuery(pydantic.BaseModel):
    visibility: Optional[VisibilityState] = None


class _BlueprintUploadQuery(pydantic.BaseModel):
    async_upload: Optional[bool] = False
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    labels: Optional[List[Any]] = []
    visibility: Optional[VisibilityState] = None
    blueprint_archive_url: Optional[str] = None
    state: Optional[str] = None
    skip_execution: Optional[bool] = False
    application_file_name: Optional[str] = ''
    private_resource: Optional[bool] = None


class _BlueprintDeleteQuery(pydantic.BaseModel):
    force: Optional[bool] = False


class BlueprintsId(resources_v2.BlueprintsId):
    @authorize('blueprint_upload')
    @rest_decorators.marshal_with(models.Blueprint)
    def put(self, blueprint_id, **kwargs):
        """
        Upload a blueprint (id specified)
        """
        rm = get_resource_manager()
        sm = get_storage_manager()
        rest_utils.validate_inputs({'blueprint_id': blueprint_id})
        args_source = None
        form_params = request.form.get('params')
        if form_params:
            args_source = json.loads(form_params)
        if not args_source:
            args_source = request.args
        args = _BlueprintUploadQuery.parse_obj(args_source)

        labels = args.labels
        visibility = args.visibility
        private_resource = args.private_resource
        application_file_name = args.application_file_name
        skip_execution = args.skip_execution
        state = args.state
        blueprint_url = args.blueprint_archive_url
        async_upload = args.async_upload

        if blueprint_url:
            if (
                request.data or  # blueprint in body (pre-7.0 client)
                'blueprint_archive' in request.files  # multipart
            ):
                raise BadParametersError(
                    "Can pass blueprint as only one of: URL via query "
                    "parameters, multi-form or chunked.")

        created_at = args.created_at
        if created_at:
            check_user_action_allowed('set_timestamp', None, True)
            created_at = rest_utils.parse_datetime_string(created_at)

        created_by = args.created_by
        if created_by:
            check_user_action_allowed('set_owner', None, True)
            created_by = rest_utils.valid_user(created_by)

        unique_labels_check = []
        for label in labels:
            parsed_key, parsed_value = rest_utils.parse_label(label['key'],
                                                              label['value'])
            label['key'] = parsed_key
            label['value'] = parsed_value
            unique_labels_check.append((parsed_key, parsed_value))
        rest_utils.test_unique_labels(unique_labels_check)

        visibility = rm.get_resource_visibility(
            models.Blueprint, blueprint_id, visibility, private_resource)

        with sm.transaction():
            if failed_bp := self._failed_blueprint(
                sm, blueprint_id, visibility,
            ):
                sm.delete(failed_bp)

        with sm.transaction():
            blueprint = models.Blueprint(
                plan=None,
                id=blueprint_id,
                description=None,
                created_at=created_at or datetime.now(),
                updated_at=datetime.now(),
                main_file_name=unquote(application_file_name),
                visibility=visibility,
                state=state or BlueprintUploadState.PENDING,
                creator=created_by,
            )
            sm.put(blueprint)

            if not blueprint_url:
                blueprint.state = BlueprintUploadState.UPLOADING

            if not skip_execution:
                blueprint.upload_execution, messages = rm.upload_blueprint(
                    blueprint_id,
                    application_file_name,
                    blueprint_url,
                    labels=labels,
                    # for the import resolver
                    file_server_root=config.instance.file_server_root,
                    marketplace_api_url=config.instance.marketplace_api_url,
                )
            else:
                messages = []
                async_upload = True

        try:
            if not blueprint_url:
                upload_manager.upload_blueprint_archive_to_file_server(
                    blueprint_id)
            if messages:
                workflow_executor.execute_workflow(messages)
        except Exception as e:
            blueprint.state = BlueprintUploadState.FAILED_UPLOADING
            blueprint.error = str(e)
            blueprint.error_traceback = traceback.format_exc()
            sm.update(blueprint)
            upload_manager.cleanup_blueprint_archive_from_file_server(
                blueprint_id, current_tenant.name)
            raise

        if not async_upload:
            return rest_utils.get_uploaded_blueprint(sm, blueprint)
        return blueprint, 201

    def _failed_blueprint(self, sm, blueprint_id, visibility):
        current_tenant = request.headers.get('tenant')
        if visibility == VisibilityState.GLOBAL:
            # TODO shouldn't this need an all_tenants=True or the like?
            existing_duplicates = sm.list(
                models.Blueprint, filters={'id': blueprint_id})
            if existing_duplicates:
                if existing_duplicates[0].state in \
                        BlueprintUploadState.FAILED_STATES:
                    return existing_duplicates[0]
                raise ConflictError(
                    f"Can't set or create the resource `{blueprint_id}`, its "
                    "visibility can't be global because it also exists in "
                    "other tenants"
                )
        else:
            existing_duplicates = sm.list(
                models.Blueprint, filters={'id': blueprint_id,
                                           'tenant_name': current_tenant})
            if existing_duplicates:
                if existing_duplicates[0].state in \
                        BlueprintUploadState.FAILED_STATES:
                    return existing_duplicates[0]
                raise ConflictError(
                    f'blueprint with id={blueprint_id} already exists on '
                    f'tenant {current_tenant} or with global visibility'
                )

    @swagger.operation(
        responseClass=models.Blueprint,
        nickname="deleteById",
        notes="deletes a blueprint by its id."
    )
    @authorize('blueprint_delete')
    def delete(self, blueprint_id, **kwargs):
        """Delete blueprint by id"""
        args = _BlueprintDeleteQuery.parse_obj(request.args)
        get_resource_manager().delete_blueprint(
            blueprint_id,
            force=args.force)
        return "", 204

    @authorize('blueprint_upload')
    @rest_decorators.marshal_with(models.Blueprint)
    def patch(self, blueprint_id, **kwargs):
        """
        Update a blueprint.

        Used for updating the blueprint's state (and error) while uploading,
        and updating the blueprint's other attributes upon a successful upload.
        This method is for internal use only.
        """
        if not request.json:
            raise IllegalActionError('Update a blueprint request must include '
                                     'at least one parameter to update')

        args = _BlueprintUpdateArgs.parse_obj(request.json)
        query = _BlueprintUpdateQuery.parse_obj(request.args)
        created_at = creator = None
        if args.created_at is not None:
            check_user_action_allowed('set_timestamp', None, True)
            created_at = rest_utils.parse_datetime_string(
                args.created_at)

        if args.creator is not None:
            check_user_action_allowed('set_owner', None, True)
            creator = rest_utils.valid_user(args.creator)

        sm = get_storage_manager()
        blueprint = sm.get(models.Blueprint, blueprint_id)
        # if finished blueprint validation - cleanup DB entry
        # and uploaded blueprints folder
        if blueprint.state == BlueprintUploadState.VALIDATING:
            # unattach .upload_execution from the blueprint before deleting it
            # so that the execution is not deleted via cascade (the user still
            # needs to be able to fetch the execution & logs to view the
            # results of validation)
            blueprint.upload_execution = None
            sm.update(blueprint)

            uploaded_blueprint_path = join(
                config.instance.file_server_root,
                FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                blueprint.tenant.name,
                blueprint.id)
            remove(uploaded_blueprint_path)
            sm.delete(blueprint)
            return blueprint

        # set blueprint visibility
        visibility = query.visibility
        if visibility:
            if visibility not in VisibilityState.STATES:
                raise BadParametersError(
                    "Invalid visibility: `{0}`. Valid visibility's values "
                    "are: {1}".format(visibility, VisibilityState.STATES)
                )
            blueprint.visibility = visibility

        # set other blueprint attributes.
        if args.plan is not None:
            blueprint.plan = args.plan
        if args.description is not None:
            blueprint.description = args.description
        if args.requirements:
            blueprint.requirements = args.requirements
        if args.main_file_name is not None:
            blueprint.main_file_name = args.main_file_name
        if creator is not None:
            blueprint.creator = creator
        if created_at is not None:
            blueprint.created_at = created_at
        if args.upload_execution is not None:
            blueprint.upload_execution = sm.get(
                models.Execution, args.upload_execution)

        if args.plan:
            imported_blueprints = args.plan\
                .get(constants.IMPORTED_BLUEPRINTS, {})
            _validate_imported_blueprints(sm, blueprint, imported_blueprints)
        # set blueprint state
        state = args.state
        if state:
            if state not in BlueprintUploadState.STATES:
                raise BadParametersError(
                    "Invalid state: `{0}`. Valid blueprint state values are: "
                    "{1}".format(state, BlueprintUploadState.STATES)
                )

            blueprint.state = state
            blueprint.error = args.error
            blueprint.error_traceback = args.error_traceback

            # On finalizing the blueprint upload, extract archive to file
            # server
            if state == BlueprintUploadState.UPLOADED:
                upload_manager. \
                    extract_blueprint_archive_to_file_server(
                        blueprint_id=blueprint_id,
                        tenant=blueprint.tenant.name)

            # If failed for any reason, cleanup the blueprint archive from
            # server
            elif state in BlueprintUploadState.FAILED_STATES:
                upload_manager. \
                    cleanup_blueprint_archive_from_file_server(
                        blueprint_id=blueprint_id,
                        tenant=blueprint.tenant.name)

        labels_list = None
        if args.labels is not None:
            raw_list = args.labels_list
            if all(
                'key' in label and 'value' in label
                for label in raw_list
            ):
                labels_list = [Label(**label)
                               for label in raw_list]
            else:
                labels_list = get_labels_list(raw_list)
        if state == BlueprintUploadState.UPLOADED and labels_list is None:
            labels_list = get_labels_from_plan(blueprint.plan,
                                               constants.BLUEPRINT_LABELS)

        if labels_list is not None:
            check_state = state or blueprint.state
            if check_state != BlueprintUploadState.UPLOADED:
                raise ConflictError(
                    'Blueprint labels can be created only if the '
                    'blueprint state is {0}'.format(
                        BlueprintUploadState.UPLOADED))
            rm = get_resource_manager()
            rm.update_resource_labels(models.BlueprintLabel,
                                      blueprint,
                                      labels_list,
                                      creator=creator,
                                      created_at=created_at)

        blueprint.updated_at = get_formatted_timestamp()
        return sm.update(blueprint)


def _validate_imported_blueprints(sm, blueprint, imported_blueprints):
    for imported_blueprint in imported_blueprints:
        if not sm.get(models.Blueprint, imported_blueprint, include=['id']):
            raise ImportedBlueprintNotFound(
                f'Blueprint {blueprint.id} uses an imported blueprint which '
                f'is unavailable: {imported_blueprint}')


class _BlueprintValidateArgs(rest_utils.SetVisibilityArgs):
    application_file_name: Optional[str] = None
    blueprint_archive_url: Optional[str] = None


class BlueprintsIdValidate(BlueprintsId):
    @authorize('blueprint_upload')
    @rest_decorators.marshal_with(models.Blueprint)
    def put(self, blueprint_id, **kwargs):
        """
        Validate a blueprint (id specified)
        """
        sm = get_storage_manager()
        rm = get_resource_manager()
        args_source = {}
        form_params = request.form.get('params')
        if form_params:
            args_source = json.loads(form_params)
        if not args_source:
            args_source = request.args.to_dict(flat=False)
        args = _BlueprintValidateArgs.parse_obj(args_source)

        visibility = args.visibility
        if visibility is not None:
            rest_utils.validate_visibility(
                visibility, valid_values=VisibilityState.STATES)

        with sm.transaction():
            blueprint = models.Blueprint(
                plan=None,
                id=blueprint_id,
                description=None,
                main_file_name=None,
                visibility=visibility,
                state=BlueprintUploadState.VALIDATING,
            )

            sm.put(blueprint)
            blueprint.upload_execution, messages = rm.upload_blueprint(
                blueprint_id,
                args.application_file_name,
                args.blueprint_archive_url,
                config.instance.file_server_root,     # for the import resolver
                config.instance.marketplace_api_url,  # for the import resolver
                validate_only=True,
            )

        try:
            if not args.blueprint_archive_url:
                upload_manager.upload_blueprint_archive_to_file_server(
                    blueprint_id)
            workflow_executor.execute_workflow(messages)
        except Exception:
            sm.delete(blueprint)
            upload_manager.cleanup_blueprint_archive_from_file_server(
                blueprint_id, current_tenant.name)
            raise
        return blueprint, 201


class BlueprintsIdArchive(resources_v1.BlueprintsIdArchive):
    @authorize('blueprint_upload')
    def put(self, blueprint_id, **kwargs):
        """
        Upload an archive for an existing a blueprint.

        Used for uploading the blueprint's archive, downloaded from a URL using
        a system workflow, to the manager's file server
        This method is for internal use only.
        """
        upload_manager. \
            upload_blueprint_archive_to_file_server(blueprint_id=blueprint_id)

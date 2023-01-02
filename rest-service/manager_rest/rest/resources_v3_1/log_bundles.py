import pydantic
import os
from typing import Optional

from flask import request

from cloudify.models_states import LogBundleState, ExecutionState

from manager_rest import config, manager_exceptions, workflow_executor
from manager_rest.persistent_storage import get_storage_handler
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.rest import rest_decorators, rest_utils, swagger
from manager_rest.storage import get_storage_manager, models
from manager_rest.resource_manager import get_resource_manager
from manager_rest.constants import FILE_SERVER_LOG_BUNDLES_FOLDER


def _get_bundle_path(bundle_id):
    return os.path.join(
        config.instance.file_server_root,
        FILE_SERVER_LOG_BUNDLES_FOLDER,
        bundle_id + '.zip'
    )


class LogBundles(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(models.LogBundle.__name__),
        nickname='list',
        notes='Returns a list of existing log bundles.'
    )
    @authorize('log_bundle_list')
    @rest_decorators.marshal_with(models.LogBundle)
    @rest_decorators.create_filters(models.LogBundle)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.LogBundle)
    @rest_decorators.search('id')
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, search=None, **kwargs):
        return get_storage_manager().list(
            models.LogBundle,
            include=_include,
            filters=filters,
            substr_filters=search,
            pagination=pagination,
            sort=sort,
        )


class _CreateLogBundleArgs(pydantic.BaseModel):
    queue: Optional[bool] = False


class _UpdateLogBundleArgs(pydantic.BaseModel):
    status: str
    error: Optional[str] = ''


class LogBundlesId(SecuredResource):
    @swagger.operation(
        responseClass=models.LogBundle,
        nickname='getById',
        notes='Returns a log bundle by its id.'
    )
    @authorize('log_bundle_get')
    @rest_decorators.marshal_with(models.LogBundle)
    def get(self, log_bundle_id, _include=None, **kwargs):
        return get_storage_manager().get(
            models.LogBundle,
            log_bundle_id,
            include=_include,
        )

    @swagger.operation(
        responseClass=models.LogBundle,
        nickname='createLogBundle',
        notes='Create a new log bundle.',
        consumes=[
            "application/json"
        ]
    )
    @authorize('log_bundle_create')
    @rest_decorators.marshal_with(models.Execution)
    def put(self, log_bundle_id):
        rest_utils.validate_inputs({'log_bundle_id': log_bundle_id})
        args = _CreateLogBundleArgs.parse_obj(request.json)
        execution, messages = get_resource_manager().create_log_bundle(
            log_bundle_id,
            args.queue,
        )
        workflow_executor.execute_workflow(messages)
        return execution, 201

    @swagger.operation(
        responseClass=models.LogBundle,
        nickname='deleteLogBundle',
        notes='Delete existing log bundle.'
    )
    @authorize('log_bundle_delete')
    @rest_decorators.marshal_with(models.LogBundle)
    def delete(self, log_bundle_id):
        sm = get_storage_manager()
        log_bundle = sm.get(models.LogBundle, log_bundle_id)
        ongoing_log_bundle_execs = sm.list(
            models.Execution,
            get_all_results=True,
            filters={
                'workflow_id': ['create_log_bundle'],
                'status': ExecutionState.ACTIVE_STATES,
            })
        for execution in ongoing_log_bundle_execs:
            if execution.parameters.get('log_bundle_id') == log_bundle_id:
                raise manager_exceptions.LogBundleActionError(
                    f'Cannot delete log bundle `{log_bundle_id}` which has '
                    f'an active `{execution.workflow_id}` execution')

        sm.delete(log_bundle)
        path = _get_bundle_path(log_bundle_id)
        if os.path.exists(path):
            os.remove(path)
        return log_bundle, 200

    @authorize('log_bundle_status_update')
    def patch(self, log_bundle_id):
        """Update log bundle status by id
        """
        args = _UpdateLogBundleArgs.parse_obj(request.json)
        log_bundle = get_storage_manager().get(models.LogBundle,
                                               log_bundle_id)
        log_bundle.status = args.status
        log_bundle.error = args.error
        get_storage_manager().update(log_bundle)


class LogBundlesIdArchive(SecuredResource):

    @swagger.operation(
        nickname='downloadLogBundle',
        notes='Downloads log bundle as an archive.'
    )
    @authorize('log_bundle_download')
    def get(self, log_bundle_id):
        bundle = get_storage_manager().get(models.LogBundle, log_bundle_id)
        if bundle.status == LogBundleState.FAILED:
            raise manager_exceptions.LogBundleActionError(
                'Failed log bundle cannot be downloaded'
            )

        log_bundle_uri = f'{FILE_SERVER_LOG_BUNDLES_FOLDER}'\
                         f'/{log_bundle_id}.zip'

        return get_storage_handler().proxy(log_bundle_uri)

import uuid
from datetime import datetime

import pydantic

from flask import request
from typing import Any, Dict, Optional

from cloudify.models_states import ExecutionState
from manager_rest import manager_exceptions, workflow_executor
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.resource_manager import (
    ResourceManager,
    get_resource_manager,
)
from manager_rest.rest import requests_schema, swagger
from manager_rest.rest.rest_decorators import (
    marshal_with,
    not_while_cancelling
)
from manager_rest.rest.rest_utils import (
    parse_datetime_string,
    valid_user,
)
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
from manager_rest.storage import (
    get_storage_manager,
    models,
)


class _ExecuteWorkflowArgs(pydantic.BaseModel):
    deployment_id: str
    workflow_id: str
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    status: Optional[ExecutionState] = None
    force_status: Optional[ExecutionState] = None
    id: Optional[str] = None
    error: Optional[Any] = ''
    allow_custom_parameters: Optional[bool] = False
    force: Optional[bool] = False
    queue: Optional[bool] = False
    dry_run: Optional[bool] = False
    parameters: Optional[Dict[str, Any]] = {}
    wait_after_fail: Optional[int] = 600
    scheduled_time: Optional[str] = None


class _ExecutionsListQuery(pydantic.BaseModel):
    deployment_id: Optional[str] = None
    include_system_workflows: Optional[bool] = False


class Executions(SecuredResource):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.Execution.__name__),
        nickname="list",
        notes="Returns a list of executions for the optionally provided "
              "deployment id.",
        parameters=[{'name': 'deployment_id',
                     'description': 'List execution of a specific deployment',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'defaultValue': None,
                     'paramType': 'query'},
                    {'name': 'include_system_workflows',
                     'description': 'Include executions of system workflows',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'bool',
                     'defaultValue': False,
                     'paramType': 'query'}]
    )
    @authorize('execution_list')
    @marshal_with(models.Execution)
    def get(self, _include=None, **kwargs):
        """List executions"""
        args = _ExecutionsListQuery.parse_obj(request.args)
        deployment_id_filter = ResourceManager.create_filters_dict(
            deployment_id=args.deployment_id)
        return get_resource_manager().list_executions(
            is_include_system_workflows=args.include_system_workflows,
            include=_include,
            filters=deployment_id_filter).items

    @authorize('execution_start')
    @not_while_cancelling
    @marshal_with(models.Execution)
    def post(self, **kwargs):
        """Execute a workflow"""
        args = _ExecuteWorkflowArgs.parse_obj(request.json)
        allow_custom_parameters = args.allow_custom_parameters
        force = args.force
        dry_run = args.dry_run
        queue = args.queue

        deployment_id = args.deployment_id
        workflow_id = args.workflow_id
        parameters = args.parameters
        wait_after_fail = args.wait_after_fail
        scheduled_time = args.scheduled_time
        force_status = args.force_status
        creator = args.created_by
        created_at = args.created_at
        started_at = args.started_at
        ended_at = args.ended_at
        execution_id = args.id
        error = args.error

        if creator:
            check_user_action_allowed('set_owner', None, True)
            creator = valid_user(creator)

        if created_at or started_at or ended_at:
            check_user_action_allowed('set_timestamp', None, True)
            if created_at:
                created_at = parse_datetime_string(created_at)
            if started_at:
                started_at = parse_datetime_string(started_at)
            if ended_at:
                ended_at = parse_datetime_string(ended_at)

        if error or force_status or execution_id or not deployment_id:
            check_user_action_allowed('set_execution_details', None, True)

        if force_status and scheduled_time:
            raise manager_exceptions.BadParametersError(
                'A status cannot be forced when scheduling an execution.'
            )

        if force_status and force_status not in ExecutionState.STATES:
            raise manager_exceptions.BadParametersError(
                'Force status was set to invalid state "{state}". '
                'Valid states are: {valid}'.format(
                    state=force_status,
                    valid=','.join(ExecutionState.STATES),
                )
            )

        if scheduled_time:
            sm = get_storage_manager()
            schedule = models.ExecutionSchedule(
                id='{}_{}'.format(workflow_id, uuid.uuid4().hex),
                deployment=sm.get(models.Deployment, deployment_id),
                created_at=datetime.utcnow(),
                since=self._parse_scheduled_time(scheduled_time),
                rule={'count': 1},
                slip=0,
                workflow_id=workflow_id,
                parameters=parameters,
                execution_arguments={
                    'allow_custom_parameters': allow_custom_parameters,
                    'force': force,
                    'is_dry_run': dry_run,
                    'wait_after_fail': wait_after_fail,
                },
                stop_on_fail=False,
            )
            schedule.next_occurrence = schedule.compute_next_occurrence()
            sm.put(schedule)
            return models.Execution(status=ExecutionState.SCHEDULED), 201

        if parameters is not None and not isinstance(parameters, dict):
            raise manager_exceptions.BadParametersError(
                f"request body's 'parameters' field must be a dict but"
                f" is of type {parameters.__class__.__name__}")

        sm = get_storage_manager()
        rm = get_resource_manager()
        with sm.transaction():
            kwargs = {
                'workflow_id': workflow_id,
                'parameters': parameters,
                'is_dry_run': dry_run,
                'status': force_status or ExecutionState.PENDING,
                'allow_custom_parameters': allow_custom_parameters,
                'force': force,
                'error': error,
            }
            deployment = None
            if deployment_id:
                deployment = sm.get(models.Deployment, deployment_id)
                rm.verify_deployment_environment_created_successfully(
                    deployment)
                kwargs['deployment'] = deployment
            execution = models.Execution(**kwargs)
            if creator:
                execution.creator = creator
            if created_at:
                execution.created_at = created_at
            if started_at:
                execution.started_at = started_at
            if ended_at:
                execution.ended_at = ended_at
            if execution_id:
                execution.id = execution_id
            sm.put(execution)
            messages = []
            if (
                force_status in ExecutionState.STATES
                and force_status not in ExecutionState.WAITING_STATES
                and force_status != ExecutionState.PENDING
            ):
                self._process_linked_executions(execution, deployment, sm)

            if not force_status:
                messages = rm.prepare_executions(
                    [execution],
                    bypass_maintenance=is_bypass_maintenance_mode(),
                    force=force,
                    queue=queue,
                    wait_after_fail=wait_after_fail,
                )
        workflow_executor.execute_workflow(messages)
        return execution, 201

    def _process_linked_executions(self, execution, deployment, sm):
        def _should_update(execution, target_entity, target_attr):
            attr = getattr(target_entity, target_attr)
            if attr is None:
                # Always update if the linked exec wasn't set
                return True
            else:
                target_time = parse_datetime_string(attr.started_at)
                if target_time < execution.started_at:
                    return True
            return False

        if deployment:
            exec_relations_set = False
            if _should_update(execution, deployment, 'latest_execution'):
                deployment.latest_execution = execution
                exec_relations_set = True

            if execution.workflow_id == \
                    'create_deployment_environment':
                if _should_update(execution, deployment, 'create_execution'):
                    deployment.create_execution = execution
                    exec_relations_set = True

            if exec_relations_set:
                sm.update(deployment)
        elif execution.workflow_id == 'upload_blueprint':
            blueprint = sm.get(models.Blueprint,
                               execution.parameters['blueprint_id'])
            if _should_update(execution, blueprint, 'upload_execution'):
                blueprint.upload_execution = execution
                sm.update(blueprint)

    def _parse_scheduled_time(self, scheduled_time):
        scheduled_utc = parse_datetime_string(scheduled_time)
        if scheduled_utc <= datetime.utcnow():
            raise manager_exceptions.BadParametersError(
                'Date `{0}` has already passed, please provide'
                ' valid date. \nExpected format: YYYYMMDDHHMM+HHMM or'
                ' YYYYMMDDHHMM-HHMM i.e: 201801012230-0500'
                ' (Jan-01-18 10:30pm EST)'.format(scheduled_time))
        return scheduled_utc


class _ExecutionAction(pydantic.BaseModel):
    action: str


class _ExecutionStatusUpdate(pydantic.BaseModel):
    status: ExecutionState
    error: Optional[str] = ''


class ExecutionsId(SecuredResource):
    @swagger.operation(
        responseClass=models.Execution,
        nickname="getById",
        notes="Returns the execution state by its id.",
    )
    @authorize('execution_get')
    @marshal_with(models.Execution)
    def get(self, execution_id, _include=None, **kwargs):
        """
        Get execution by id
        """
        return get_storage_manager().get(
            models.Execution,
            execution_id,
            include=_include
        )

    @swagger.operation(
        responseClass=models.Execution,
        nickname="modify_state",
        notes="Modifies a running execution state (currently, only cancel"
              " and force-cancel are supported)",
        parameters=[{'name': 'body',
                     'description': 'json with an action key. '
                                    'Legal values for action are: [cancel,'
                                    ' force-cancel]',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.ModifyExecutionRequest.__name__,  # NOQA
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @authorize('execution_cancel')
    @marshal_with(models.Execution)
    def post(self, execution_id, **kwargs):
        """
        Apply execution action (cancel, force-cancel) by id
        """
        args = _ExecutionAction.parse_obj(request.json)
        action = args.action

        valid_actions = ['cancel', 'force-cancel', 'kill', 'resume',
                         'force-resume', 'requeue']

        if action not in valid_actions:
            raise manager_exceptions.BadParametersError(
                'Invalid action: {0}, Valid action values are: {1}'.format(
                    action, valid_actions))

        if action in ('resume', 'force-resume'):
            return get_resource_manager().resume_execution(
                execution_id, force=action == 'force-resume')
        return get_resource_manager().cancel_execution(
            execution_id, action == 'force-cancel', action == 'kill')

    @swagger.operation(
        responseClass=models.Execution,
        nickname="updateExecutionStatus",
        notes="Updates the execution's status",
        parameters=[{'name': 'status',
                     'description': "The execution's new status",
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'},
                    {'name': 'error',
                     'description': "An error message. If omitted, "
                                    "error will be updated to an empty "
                                    "string",
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @authorize('execution_status_update')
    @marshal_with(models.Execution)
    def patch(self, execution_id, **kwargs):
        """Update execution status by id"""
        args = _ExecutionStatusUpdate.parse_obj(request.json)
        return get_resource_manager().update_execution_status(
            execution_id,
            args.status,
            args.error,
        )

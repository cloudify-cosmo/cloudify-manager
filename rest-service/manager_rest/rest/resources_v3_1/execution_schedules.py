import pydantic
from typing import Any, Dict, List, Optional


from flask import request

from manager_rest import manager_exceptions
from manager_rest.rest import rest_decorators, swagger
from manager_rest.rest.rest_utils import (
    validate_inputs,
    parse_datetime_multiple_formats,
    parse_datetime_string,
    compute_rule_from_scheduling_params,
    valid_user,
)
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
from manager_rest.storage import get_storage_manager, models
from manager_rest.resource_manager import get_resource_manager
from manager_rest.utils import get_formatted_timestamp


class ExecutionSchedules(SecuredResource):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.ExecutionSchedule.__name__),
        nickname='list',
        notes='Returns a list of existing execution schedules.'
    )
    @authorize('execution_schedule_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.ExecutionSchedule)
    @rest_decorators.create_filters(models.ExecutionSchedule)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.ExecutionSchedule)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, all_tenants=None, search=None, **kwargs):
        return get_storage_manager().list(
            models.ExecutionSchedule,
            include=_include,
            filters=filters,
            substr_filters=search,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants
        )


class _ExecutionArguments(pydantic.BaseModel):
    allow_custom_parameters: Optional[bool] = False
    force: Optional[bool] = False
    dry_run: Optional[bool] = False
    wait_after_fail: Optional[int] = 600


class _CreateScheduleArgs(pydantic.BaseModel):
    workflow_id: str
    since: str
    until: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    slip: Optional[int] = 0
    stop_on_fail: Optional[bool] = False
    enabled: Optional[bool] = True
    rrule: Optional[str] = None
    recurrence: Optional[str] = None
    weekdays: Optional[List[str]] = None
    count: Optional[int] = None
    execution_arguments: Optional[_ExecutionArguments] = None


class _HasDeploymentID(pydantic.BaseModel):
    deployment_id: str


class _UpdateScheduleArgs(pydantic.BaseModel):
    enabled: Optional[bool] = None
    stop_on_fail: Optional[bool] = None
    slip: Optional[int] = None
    since: Optional[str] = None
    until: Optional[str] = None
    workflow_id: Optional[str] = None
    rrule: Optional[str] = None
    recurrence: Optional[str] = None
    weekdays: Optional[List[str]] = None
    count: Optional[int] = None


class ExecutionSchedulesId(SecuredResource):
    @rest_decorators.marshal_with(models.ExecutionSchedule)
    @authorize('execution_schedule_create')
    def put(self, schedule_id, **kwargs):
        """Schedule a workflow execution"""

        validate_inputs({'schedule_id': schedule_id})
        deployment_id = _HasDeploymentID.parse_obj(request.args).deployment_id
        args = _CreateScheduleArgs.parse_obj(request.json)
        created_at = creator = None
        if args.created_at:
            check_user_action_allowed('set_timestamp', None, True)
            created_at = parse_datetime_string(args.created_at)

        if args.created_by:
            check_user_action_allowed('set_owner', None, True)
            creator = valid_user(args.created_by)

        if args.execution_arguments:
            execution_arguments = args.execution_arguments.dict()
        else:
            execution_arguments = {}

        # rename dry_run -> is_dry_run
        execution_arguments['is_dry_run'] = \
            execution_arguments.pop('dry_run', False)

        parameters = args.parameters
        if parameters is not None and not isinstance(parameters, dict):
            raise manager_exceptions.BadParametersError(
                "parameters: expected a dict, but got: {0}".format(parameters))

        rm = get_resource_manager()
        deployment = rm.sm.get(models.Deployment, deployment_id)
        rm._verify_workflow_in_deployment(args.workflow_id,
                                          deployment,
                                          deployment_id)

        since = args.since
        until = args.until
        if since:
            since = parse_datetime_multiple_formats(since)
        if until:
            until = parse_datetime_multiple_formats(until)
        rule = compute_rule_from_scheduling_params(args)
        slip = args.slip
        now = get_formatted_timestamp()
        schedule = models.ExecutionSchedule(
            id=schedule_id,
            deployment=deployment,
            created_at=created_at or now,
            since=since,
            until=until,
            rule=rule,
            slip=slip,
            workflow_id=args.workflow_id,
            parameters=parameters,
            execution_arguments=execution_arguments,
            stop_on_fail=args.stop_on_fail,
            enabled=args.enabled,
        )
        if creator:
            schedule.creator = creator
        schedule.next_occurrence = schedule.compute_next_occurrence()
        return rm.sm.put(schedule), 201

    @rest_decorators.marshal_with(models.ExecutionSchedule)
    @authorize('execution_schedule_create')
    def patch(self, schedule_id, **kwargs):
        """Updates scheduling parameters of an existing execution schedule"""
        deployment_id = _HasDeploymentID.parse_obj(request.args).deployment_id
        sm = get_storage_manager()
        schedule = sm.get(
            models.ExecutionSchedule,
            None,
            filters={'id': schedule_id,  'deployment_id': deployment_id}
        )
        args = _UpdateScheduleArgs.parse_obj(request.json)

        if args.since:
            schedule.since = parse_datetime_multiple_formats(args.since)
        if args.until:
            schedule.until = parse_datetime_multiple_formats(args.until)
        if args.workflow_id:
            schedule.workflow_id = args.workflow_id
        if args.slip is not None:
            schedule.slip = args.slip
        if args.stop_on_fail is not None:
            schedule.stop_on_fail = args.stop_on_fail
        if args.enabled is not None:
            schedule.enabled = args.enabled
        schedule.rule = compute_rule_from_scheduling_params(
            args, existing_rule=schedule.rule)
        schedule.next_occurrence = schedule.compute_next_occurrence()
        sm.update(schedule)
        return schedule, 201

    @swagger.operation(
        responseClass=models.ExecutionSchedule,
        nickname="getById",
        notes="Returns the execution schedule by its id.",
    )
    @authorize('execution_schedule_get')
    @rest_decorators.marshal_with(models.ExecutionSchedule)
    def get(self, schedule_id, _include=None, **kwargs):
        """
        Get execution schedule by id
        """
        deployment_id = _HasDeploymentID.parse_obj(request.args).deployment_id
        return get_storage_manager().get(
            models.ExecutionSchedule,
            None,
            filters={'id': schedule_id, 'deployment_id': deployment_id},
            include=_include
        )

    @authorize('execution_schedule_create')
    def delete(self, schedule_id):
        deployment_id = _HasDeploymentID.parse_obj(request.args).deployment_id
        sm = get_storage_manager()
        schedule = sm.get(
            models.ExecutionSchedule,
            None,
            filters={'id': schedule_id, 'deployment_id': deployment_id})
        sm.delete(schedule)
        return "", 204

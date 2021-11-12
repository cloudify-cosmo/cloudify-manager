from flask import request
from flask_restful_swagger import swagger
from flask_restful.reqparse import Argument

from cloudify._compat import text_type

from manager_rest import manager_exceptions
from manager_rest.rest import rest_decorators
from manager_rest.rest.rest_utils import (
    get_json_and_verify_params,
    verify_and_convert_bool,
    validate_inputs,
    get_args_and_verify_arguments,
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


class ExecutionSchedulesId(SecuredResource):
    @rest_decorators.marshal_with(models.ExecutionSchedule)
    @authorize('execution_schedule_create')
    def put(self, schedule_id, **kwargs):
        """Schedule a workflow execution"""

        validate_inputs({'schedule_id': schedule_id})
        deployment_id = get_args_and_verify_arguments([
            Argument('deployment_id', type=text_type, required=True),
        ])['deployment_id']
        request_dict = get_json_and_verify_params({'workflow_id',
                                                   'since'})

        created_at = creator = None
        if request_dict.get('created_at'):
            check_user_action_allowed('set_timestamp', None, True)
            created_at = parse_datetime_string(request_dict['created_at'])

        if request_dict.get('creator'):
            check_user_action_allowed('set_creator', None, True)
            creator = valid_user(request_dict['creator'])

        workflow_id = request_dict['workflow_id']
        execution_arguments = self._get_execution_arguments(request_dict)
        parameters = request_dict.get('parameters', None)
        if parameters is not None and not isinstance(parameters, dict):
            raise manager_exceptions.BadParametersError(
                "parameters: expected a dict, but got: {0}".format(parameters))

        rm = get_resource_manager()
        deployment = rm.sm.get(models.Deployment, deployment_id)
        rm._verify_workflow_in_deployment(workflow_id,
                                          deployment,
                                          deployment_id)

        since = request_dict['since']
        until = request_dict.get('until')
        if since:
            since = parse_datetime_multiple_formats(since)
        if until:
            until = parse_datetime_multiple_formats(until)
        rule = compute_rule_from_scheduling_params(request_dict)
        slip = request_dict.get('slip', 0)
        stop_on_fail = verify_and_convert_bool(
            'stop_on_fail',  request_dict.get('stop_on_fail', False))
        now = get_formatted_timestamp()
        schedule = models.ExecutionSchedule(
            id=schedule_id,
            deployment=deployment,
            created_at=created_at or now,
            since=since,
            until=until,
            rule=rule,
            slip=slip,
            workflow_id=workflow_id,
            parameters=parameters,
            execution_arguments=execution_arguments,
            stop_on_fail=stop_on_fail,
        )
        if creator:
            schedule.creator = creator
        schedule.next_occurrence = schedule.compute_next_occurrence()
        return rm.sm.put(schedule), 201

    @rest_decorators.marshal_with(models.ExecutionSchedule)
    @authorize('execution_schedule_create')
    def patch(self, schedule_id, **kwargs):
        """Updates scheduling parameters of an existing execution schedule"""

        deployment_id = get_args_and_verify_arguments([
            Argument('deployment_id', type=text_type, required=True)
        ])['deployment_id']
        sm = get_storage_manager()
        schedule = sm.get(
            models.ExecutionSchedule,
            None,
            filters={'id': schedule_id,  'deployment_id': deployment_id}
        )
        slip = request.json.get('slip')
        stop_on_fail = request.json.get('stop_on_fail')
        enabled = request.json.get('enabled')

        since = request.json.get('since')
        until = request.json.get('until')
        if since:
            schedule.since = parse_datetime_multiple_formats(since)
        if until:
            schedule.until = parse_datetime_multiple_formats(until)
        if slip is not None:
            schedule.slip = slip
        if stop_on_fail is not None:
            schedule.stop_on_fail = verify_and_convert_bool('stop_on_fail',
                                                            stop_on_fail)
        if enabled is not None:
            schedule.enabled = verify_and_convert_bool('enabled', enabled)
        schedule.rule = compute_rule_from_scheduling_params(
            request.json, existing_rule=schedule.rule)
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
        deployment_id = get_args_and_verify_arguments([
            Argument('deployment_id', type=text_type, required=True)
        ])['deployment_id']
        return get_storage_manager().get(
            models.ExecutionSchedule,
            None,
            filters={'id': schedule_id, 'deployment_id': deployment_id},
            include=_include
        )

    @authorize('execution_schedule_create')
    def delete(self, schedule_id):
        deployment_id = get_args_and_verify_arguments([
            Argument('deployment_id', type=text_type, required=True)
        ])['deployment_id']
        sm = get_storage_manager()
        schedule = sm.get(
            models.ExecutionSchedule,
            None,
            filters={'id': schedule_id, 'deployment_id': deployment_id})
        sm.delete(schedule)
        return None, 204

    @staticmethod
    def _get_execution_arguments(request_dict):
        arguments = request_dict.get('execution_arguments')
        if not arguments:
            return {}
        if not isinstance(arguments, dict):
            raise manager_exceptions.BadParametersError(
                "execution_arguments: expected a dict, but got: {}"
                .format(arguments))
        return {
            'allow_custom_parameters': verify_and_convert_bool(
                'allow_custom_parameters',
                arguments.get('allow_custom_parameters', False)),
            'force': verify_and_convert_bool(
                'force',
                arguments.get('force', False)),
            'is_dry_run': verify_and_convert_bool(
                'dry_run',
                arguments.get('dry_run', False)),
            'wait_after_fail': arguments.get('wait_after_fail', 600)
        }

from dateutil import rrule
from flask import request
from flask_restful_swagger import swagger

from manager_rest import manager_exceptions
from manager_rest.rest import rest_decorators
from manager_rest.rest.rest_utils import (
    get_json_and_verify_params,
    verify_and_convert_bool,
    convert_to_int,
    validate_inputs,
    parse_datetime_multiple_formats
)
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import get_storage_manager, models
from manager_rest.resource_manager import get_resource_manager
from manager_rest.utils import get_formatted_timestamp, parse_frequency


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
        request_dict = get_json_and_verify_params({'deployment_id',
                                                   'workflow_id',
                                                   'since',
                                                   'slip'})

        workflow_id = request_dict['workflow_id']
        execution_arguments = self._get_execution_arguments(request_dict)
        parameters = request_dict.get('parameters', None)
        if parameters is not None and not isinstance(parameters, dict):
            raise manager_exceptions.BadParametersError(
                "parameters: expected a dict, but got: {0}".format(parameters))

        rm = get_resource_manager()
        deployment_id = request_dict['deployment_id']
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
        rule = self._compute_rule_from_scheduling_params(request_dict)
        slip = request_dict['slip']
        stop_on_fail = verify_and_convert_bool(
            'stop_on_fail',  request_dict.get('stop_on_fail', False))
        now = get_formatted_timestamp()
        schedule = models.ExecutionSchedule(
            id=schedule_id,
            deployment=deployment,
            created_at=now,
            since=since,
            until=until,
            rule=rule,
            slip=slip,
            workflow_id=workflow_id,
            parameters=parameters,
            execution_arguments=execution_arguments,
            stop_on_fail=stop_on_fail,
        )
        schedule.next_occurrence = schedule.compute_next_occurrence()
        return rm.sm.put(schedule), 201

    @rest_decorators.marshal_with(models.ExecutionSchedule)
    @authorize('execution_schedule_create')
    def patch(self, schedule_id, **kwargs):
        """Updates scheduling parameters of an existing execution schedule"""

        sm = get_storage_manager()
        schedule = sm.get(models.ExecutionSchedule, schedule_id)
        slip = request.json.get('slip')
        stop_on_fail = request.json.get('stop_on_fail')

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
        schedule.rule = self._compute_rule_from_scheduling_params(
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
        # TODO :: include in response: number of executions already run,
        #         of them - number succeeded + number failed

        return get_storage_manager().get(
            models.ExecutionSchedule,
            schedule_id,
            include=_include
        )

    @authorize('execution_schedule_create')
    def delete(self, schedule_id):
        sm = get_storage_manager()
        schedule = sm.get(models.ExecutionSchedule, schedule_id)
        sm.delete(schedule)
        return None, 204

    @staticmethod
    def _verify_frequency(frequency_str):
        if not frequency_str:
            return
        _, frequency = parse_frequency(frequency_str)
        if not frequency:
            raise manager_exceptions.BadParametersError(
                "`{}` is not a legal frequency expression. Supported format "
                "is: <number> seconds|minutes|hours|days|weeks|months|years"
                .format(frequency_str))
        return frequency_str

    @staticmethod
    def _verify_weekdays(weekdays):
        if not weekdays:
            return
        if not isinstance(weekdays, list):
            raise manager_exceptions.BadParametersError(
                "weekdays: expected a list, but got: {}".format(weekdays))
        weekdays_caps = set(d.upper() for d in weekdays)
        valid_weekdays = {str(d) for d in rrule.weekdays}
        invalid_weekdays = weekdays_caps - valid_weekdays
        if invalid_weekdays:
            raise manager_exceptions.BadParametersError(
                "weekdays list contains invalid weekdays `{}`. Valid "
                "weekdays are: {} or their lowercase values."
                .format(invalid_weekdays, '|'.join(valid_weekdays)))
        return list(weekdays_caps)

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
            'dry_run': verify_and_convert_bool(
                'dry_run',
                arguments.get('dry_run', False)),
            'queue': verify_and_convert_bool(
                'queue',
                arguments.get('queue', False)),
            'wait_after_fail': arguments.get('wait_after_fail', 600)
        }

    def _compute_rule_from_scheduling_params(self, request_dict,
                                             existing_rule=None):
        rrule_string = request_dict.get('rrule')
        frequency = request_dict.get('frequency')
        weekdays = request_dict.get('weekdays')
        count = request_dict.get('count')

        # we need to have at least: rrule; or count=1; or frequency
        if rrule_string:
            if frequency or weekdays or count:
                raise manager_exceptions.BadParametersError(
                    "`rrule` cannot be provided together with `frequency`, "
                    "`weekdays` or `count`.")
            try:
                rrule.rrulestr(rrule_string)
            except ValueError as e:
                raise manager_exceptions.BadParametersError(
                    "invalid RRULE string provided: {}".format(e))
            return {'rrule': rrule_string}
        else:
            if count:
                count = convert_to_int(request_dict.get('count'))
            frequency = self._verify_frequency(request_dict.get('frequency'))
            weekdays = self._verify_weekdays(request_dict.get('weekdays'))
            if existing_rule:
                count = count or existing_rule.get('count')
                frequency = frequency or existing_rule.get('frequency')
                weekdays = weekdays or existing_rule.get('weekdays')

            if not frequency and count != 1:
                raise manager_exceptions.BadParametersError(
                    "frequency must be specified for execution count larger "
                    "than 1")
            return {
                'frequency': frequency,
                'count': count,
                'weekdays': weekdays
            }

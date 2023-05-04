#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

from typing import List, Optional, Type, Dict, Tuple

import pydantic
from flask import request
from dateutil import rrule

from manager_rest.rest import rest_decorators, rest_utils
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import get_storage_manager, models
from manager_rest.storage.models_base import SQLModelBase
from manager_rest import manager_exceptions

from cloudify_rest_client.responses import ListResponse

from functools import wraps


class SummaryFieldBase(str):
    """A str field with a set of allowed values, with a custom error message

    This is just a regular field, but it will show the allowed fields in
    a custom format, in the validation error message.

    To use this with a given set of allowed fields, create a subclass of this
    by using .with_allowed_values
    """
    @classmethod
    def with_allowed_values(cls, allowed_values):
        return type(
            'AllowedSummaryField',
            (cls, ),
            {'allowed_values': allowed_values},
        )

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        if value not in cls.allowed_values:
            raise ValueError(
                f'Invalid summary field: {value}. '
                f'Allowed values: { ", ".join(cls.allowed_values) }'
            )
        return value


def parse_summary_request(summary_fields):
    """Load the summary request args.

    Use this for all summary requests, to parse and validate the request
    arguments, including target_field and subfield.
    """
    allowed_choices_field = SummaryFieldBase.with_allowed_values(
        summary_fields,
    )
    summary_model = pydantic.create_model(
        'SummaryRequest',
        target_field=(
            allowed_choices_field,
            pydantic.Field(alias='_target_field')
        ),
        subfield=(
            Optional[allowed_choices_field],
            pydantic.Field(alias='_sub_field')
        ),
        get_all_results=(
            Optional[bool],
            pydantic.Field(alias='_get_all_results', default=False),
        )
    )

    def _deco(f):
        @wraps(f)
        def _inner(*args, **kwargs):
            parsed = summary_model.parse_obj(request.args)
            kwargs.update(parsed.dict())
            return f(*args, **kwargs)
        return _inner
    return _deco


class BaseSummary(SecuredResource):
    summary_fields: List[str] = []
    auth_req: Optional[str] = None
    model: Optional[Type[SQLModelBase]] = None

    def get(
        self,
        *,
        target_field,
        subfield=None,
        pagination=None,
        all_tenants=None,
        filters=None,
        get_all_results=False,
    ):
        return get_storage_manager().summarize(
            target_field=target_field,
            sub_field=subfield,
            model_class=self.model,
            pagination=pagination,
            all_tenants=all_tenants,
            get_all_results=get_all_results,
            filters=filters,
        )


def marshal_summary(summary_type):
    def build_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            target_field = request.args.get('_target_field')
            subfield = request.args.get('_sub_field')

            marshalled_items = {}
            for item in result.items:
                if item[0] not in marshalled_items:
                    marshalled_items[item[0]] = {
                        target_field: item[0],
                        summary_type: 0,
                    }

                if subfield:
                    subfield_key = 'by {0}'.format(subfield)
                    if subfield_key not in marshalled_items[item[0]]:
                        marshalled_items[item[0]][subfield_key] = []
                    marshalled_items[item[0]][subfield_key].append({
                        subfield: item[1],
                        summary_type: item[-1],
                    })
                marshalled_items[item[0]][summary_type] += item[-1]

            return {"items": list(marshalled_items.values()),
                    "metadata": result.metadata}
        return wrapper
    return build_wrapper


class SummarizeDeployments(BaseSummary):
    auth_req = 'deployment_list'
    model = models.Deployment

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('deployments')
    @rest_decorators.all_tenants
    @rest_decorators.create_filters(models.Deployment)
    @rest_decorators.paginate
    @parse_summary_request([
        'blueprint_id',
        'tenant_name',
        'visibility',
        'site_name',
        'deployment_status',
    ])
    def get(self, *args, **kwargs):
        return super(SummarizeDeployments, self).get(*args, **kwargs)


class SummarizeNodes(BaseSummary):
    auth_req = 'node_list'
    model = models.Node

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('nodes')
    @rest_decorators.create_filters(models.Node)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
    @parse_summary_request([
        'deployment_id',
        'tenant_name',
        'visibility',
    ])
    def get(self, *args, **kwargs):
        return super(SummarizeNodes, self).get(*args, **kwargs)


class SummarizeNodeInstances(BaseSummary):
    auth_req = 'node_instance_list'
    model = models.NodeInstance

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('node_instances')
    @rest_decorators.create_filters(models.NodeInstance)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
    @parse_summary_request([
        'deployment_id',
        'index',
        'node_id',
        'state',
        'host_id',
        'tenant_name',
        'visibility',
    ])
    def get(self, *args, **kwargs):
        return super(SummarizeNodeInstances, self).get(*args, **kwargs)


class SummarizeExecutions(BaseSummary):
    auth_req = 'execution_list'
    model = models.Execution

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('executions')
    @rest_decorators.create_filters(models.Execution)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
    @parse_summary_request([
        'status',
        'status_display',
        'blueprint_id',
        'deployment_id',
        'workflow_id',
        'tenant_name',
        'visibility',
    ])
    def get(self, *, target_field, subfield, **kwargs):
        postprocess = None

        # sm.summarize doesn't play nicely with the status_display
        # property; this is just a rename though, so if the user wants to
        # summarize on status_display, let's just summarize on status
        # instead, and then postprocess the result, to relabel the
        # status into status_display
        if target_field == 'status_display':
            target_field = 'status'
            postprocess = self._postprocess_target_status_display
        if subfield == 'status_display':
            subfield = 'status'
            postprocess = self.postprocess_subfield_status_display

        summary = super(SummarizeExecutions, self).get(
            target_field=target_field,
            subfield=subfield,
            **kwargs,
        )

        if postprocess is None:
            return summary

        rewritten_summary = [
            postprocess(item) for item in summary
        ]
        return ListResponse(rewritten_summary, metadata=summary.metadata)

    @staticmethod
    def _postprocess_target_status_display(item):
        # if we're postprocessing target_field, there can either be 2 fields
        # in each item (no subfield) or 3 (including subfield)
        if len(item) == 2:
            field_value, count = item
            field_value = models.Execution.STATUS_DISPLAY_NAMES.get(
                field_value, field_value,
            )
            return (field_value, count)
        elif len(item) == 3:
            field_value, subfield_value, count = item
            field_value = models.Execution.STATUS_DISPLAY_NAMES.get(
                field_value, field_value,
            )
            return (field_value, subfield_value, count)
        else:
            return item

    @staticmethod
    def postprocess_subfield_status_display(item):
        # when we're postprocessing subfield, there's always going to be
        # 3 attributes in each item
        field_value, subfield_value, count = item
        subfield_value = models.Execution.STATUS_DISPLAY_NAMES.get(
            subfield_value, subfield_value,
        )
        return (field_value, subfield_value, count)


class SummarizeBlueprints(BaseSummary):
    auth_req = 'blueprint_list'
    model = models.Blueprint

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('blueprints')
    @rest_decorators.all_tenants
    @rest_decorators.create_filters(models.Blueprint)
    @rest_decorators.paginate
    @parse_summary_request([
        'tenant_name',
        'visibility',
    ])
    def get(self, *args, **kwargs):
        return super(SummarizeBlueprints, self).get(*args, **kwargs)


class SummarizeExecutionSchedules(BaseSummary):
    auth_req = 'execution_schedule_list'
    model = models.ExecutionSchedule

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('execution_schedules')
    @rest_decorators.all_tenants
    @rest_decorators.create_filters(models.ExecutionSchedule)
    @rest_decorators.paginate
    @parse_summary_request([
        'deployment_id',
        'workflow_id',
        'tenant_name',
        'visibility',
    ])
    def get(self, *args, **kwargs):
        target_field = request.args.get('_target_field')
        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        if target_field not in self.summary_fields:
            raise manager_exceptions.BadParametersError(
                'Field {target} is not available for summary. Valid fields '
                'are: {valid}'.format(
                    target=target_field,
                    valid=', '.join(self.summary_fields),
                )
            )
        schedules_list = get_storage_manager().list(
            models.ExecutionSchedule,
            pagination=kwargs.get('pagination'),
            all_tenants=kwargs.get('all_tenants'),
            get_all_results=get_all_results,
            filters=kwargs.get('filters'),
        )
        summary_dict: Dict[Tuple, int] = {}
        for schedule in schedules_list:
            recurring = self.is_recurring(schedule.rule)
            key = (getattr(schedule, target_field),
                   'recurring' if recurring else 'single')
            summary_dict[key] = summary_dict.get(key, 0) + 1

        summary_list = []
        for k, v in summary_dict.items():
            summary_list.append(k + (v,))

        metadata = schedules_list.metadata
        schedules_list.metadata['pagination']['total'] = len(summary_dict)
        return ListResponse(summary_list, metadata)

    @staticmethod
    def is_recurring(rule):
        if 'recurrence' in rule and rule.get('count') != 1:
            return True
        if 'rrule' in rule:
            rrule_dates = rrule.rrulestr(rule['rrule'])
            try:
                if rrule_dates[1]:
                    return True
            except IndexError:
                return False
        return False

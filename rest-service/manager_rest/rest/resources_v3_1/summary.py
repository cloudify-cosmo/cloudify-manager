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

from .. import rest_utils
from flask import request
from dateutil import rrule
from manager_rest.rest import rest_decorators
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import get_storage_manager, models
from manager_rest.storage.models_base import SQLModelBase
from manager_rest import manager_exceptions

from cloudify_rest_client.responses import ListResponse

from functools import wraps


class _SummaryQuery(rest_utils.ListQuery):
    _target_field: Optional[str] = None
    _sub_field: Optional[str] = None


class BaseSummary(SecuredResource):
    summary_fields: List[str] = []
    auth_req: Optional[str] = None
    model: Optional[Type[SQLModelBase]] = None

    def get(self, pagination=None, filters=None):
        args = _SummaryQuery.parse_obj(request.args)
        target_field = args._target_field
        subfield = args._sub_field

        if target_field not in self.summary_fields:
            raise manager_exceptions.BadParametersError(
                'Field {target} is not available for summary. Valid fields '
                'are: {valid}'.format(
                    target=target_field,
                    valid=', '.join(self.summary_fields),
                )
            )

        if subfield and subfield not in self.summary_fields:
            raise manager_exceptions.BadParametersError(
                'Field {target} is not available for summary. Valid fields '
                'are: {valid}'.format(
                    target=subfield,
                    valid=', '.join(self.summary_fields),
                )
            )

        return get_storage_manager().summarize(
            target_field=target_field,
            sub_field=subfield,
            model_class=self.model,
            pagination=pagination,
            all_tenants=args.all_tenants,
            get_all_results=args.get_all_results,
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
    summary_fields = [
        'blueprint_id',
        'tenant_name',
        'visibility',
        'site_name',
        'deployment_status',
    ]
    auth_req = 'deployment_list'
    model = models.Deployment

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('deployments')
    @rest_decorators.create_filters(models.Deployment)
    @rest_decorators.paginate
    def get(self, *args, **kwargs):
        return super(SummarizeDeployments, self).get(*args, **kwargs)


class SummarizeNodes(BaseSummary):
    summary_fields = [
        'deployment_id',
        'tenant_name',
        'visibility',
    ]
    auth_req = 'node_list'
    model = models.Node

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('nodes')
    @rest_decorators.create_filters(models.Node)
    @rest_decorators.paginate
    def get(self, *args, **kwargs):
        return super(SummarizeNodes, self).get(*args, **kwargs)


class SummarizeNodeInstances(BaseSummary):
    summary_fields = [
        'deployment_id',
        'index',
        'node_id',
        'state',
        'host_id',
        'tenant_name',
        'visibility',
    ]
    auth_req = 'node_instance_list'
    model = models.NodeInstance

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('node_instances')
    @rest_decorators.create_filters(models.NodeInstance)
    @rest_decorators.paginate
    def get(self, *args, **kwargs):
        return super(SummarizeNodeInstances, self).get(*args, **kwargs)


class SummarizeExecutions(BaseSummary):
    summary_fields = [
        'status',
        'status_display',
        'blueprint_id',
        'deployment_id',
        'workflow_id',
        'tenant_name',
        'visibility',
    ]
    auth_req = 'execution_list'
    model = models.Execution

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('executions')
    @rest_decorators.create_filters(models.Execution)
    @rest_decorators.paginate
    def get(self, *args, **kwargs):
        return super(SummarizeExecutions, self).get(*args, **kwargs)


class SummarizeBlueprints(BaseSummary):
    summary_fields = [
        'tenant_name',
        'visibility',
    ]
    auth_req = 'blueprint_list'
    model = models.Blueprint

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('blueprints')
    @rest_decorators.create_filters(models.Blueprint)
    @rest_decorators.paginate
    def get(self, *args, **kwargs):
        return super(SummarizeBlueprints, self).get(*args, **kwargs)


class SummarizeExecutionSchedules(BaseSummary):
    summary_fields = [
        'deployment_id',
        'workflow_id',
        'tenant_name',
        'visibility',
    ]
    auth_req = 'execution_schedule_list'
    model = models.ExecutionSchedule

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('execution_schedules')
    @rest_decorators.create_filters(models.ExecutionSchedule)
    @rest_decorators.paginate
    def get(self, *args, **kwargs):
        args = _SummaryQuery.parse_obj(request.args)
        target_field = args._target_field

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
            all_tenants=args.all_tenants,
            get_all_results=args.get_all_results,
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

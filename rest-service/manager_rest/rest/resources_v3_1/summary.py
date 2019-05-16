from .. import rest_utils
from flask import request
from manager_rest.rest import rest_decorators
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import (get_storage_manager,
                                  models)
from manager_rest import manager_exceptions

from functools import wraps


class BaseSummary(SecuredResource):
    summary_fields = []
    auth_req = None
    model = None

    def get(self, pagination=None, all_tenants=None, filters=None):
        target_field = request.args.get('_target_field')
        subfield = request.args.get('_sub_field')

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

            return {"items": marshalled_items.values(),
                    "metadata": result.metadata}
        return wrapper
    return build_wrapper


class SummarizeDeployments(BaseSummary):
    summary_fields = [
        'blueprint_id',
        'tenant_name',
        'visibility',
        'site_name',
    ]
    auth_req = 'deployment_list'
    model = models.Deployment

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary('deployments')
    @rest_decorators.exceptions_handled
    @rest_decorators.all_tenants
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
    @rest_decorators.exceptions_handled
    @rest_decorators.create_filters(models.Node)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
    def get(self, *args, **kwargs):
        return super(SummarizeNodes, self).get(*args, **kwargs)


class SummarizeNodeInstances(BaseSummary):
    summary_fields = [
        'deployment_id',
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
    @rest_decorators.exceptions_handled
    @rest_decorators.create_filters(models.NodeInstance)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
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
    @rest_decorators.exceptions_handled
    @rest_decorators.create_filters(models.Execution)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
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
    @rest_decorators.exceptions_handled
    @rest_decorators.all_tenants
    @rest_decorators.create_filters(models.Blueprint)
    @rest_decorators.paginate
    def get(self, *args, **kwargs):
        return super(SummarizeBlueprints, self).get(*args, **kwargs)

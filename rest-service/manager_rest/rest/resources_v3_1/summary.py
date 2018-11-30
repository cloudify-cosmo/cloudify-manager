from .. import rest_utils
from flask import request
from manager_rest.rest import rest_decorators
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import (get_storage_manager,
                                  models)
from manager_rest import manager_exceptions


class BaseSummary(SecuredResource):
    summary_fields = []
    auth_req = None
    model = None

    def get(self, pagination=None, all_tenants=None, filters=None):
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

        return get_storage_manager().summarize(
            target_field=target_field,
            model_class=self.model,
            pagination=pagination,
            all_tenants=all_tenants,
            get_all_results=get_all_results,
            filters=filters,
        )


def marshal_summary(func):
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        items = [{item[0]: item[1]} for item in result.items]
        return {"items": items, "metadata": result.metadata}
    return wrapper


class SummarizeDeployments(BaseSummary):
    summary_fields = [
        'blueprint_id',
    ]
    auth_req = 'deployment_list'
    model = models.Deployment

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary
    @rest_decorators.exceptions_handled
    @rest_decorators.all_tenants
    @rest_decorators.create_filters(models.Deployment)
    @rest_decorators.paginate
    def get(self, *args, **kwargs):
        return super(SummarizeDeployments, self).get(*args, **kwargs)


class SummarizeNodes(BaseSummary):
    summary_fields = [
        'deployment_id',
    ]
    auth_req = 'node_list'
    model = models.Node

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary
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
    ]
    auth_req = 'node_instance_list'
    model = models.NodeInstance

    @authorize(auth_req, allow_all_tenants=True)
    @marshal_summary
    @rest_decorators.exceptions_handled
    @rest_decorators.create_filters(models.NodeInstance)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
    def get(self, *args, **kwargs):
        return super(SummarizeNodeInstances, self).get(*args, **kwargs)

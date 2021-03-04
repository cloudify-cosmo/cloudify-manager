from collections import OrderedDict

from cloudify._compat import text_type

from manager_rest import manager_exceptions
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager

from ..responses_v2 import ListResponse
from .. import rest_decorators, rest_utils
from ..filters_utils import create_filter_rules_list


class ResourceSearches(SecuredResource):
    def post(self, resource_model, _include):
        """List resource items

        The payload for this request is of the following form:
        {
          include = [<list of columns to include in the response>],
          filters = {<column_name>: <}
          A dictionary where keys are column names to
                        filter by, and values are values applicable for those
                        columns (or lists of such values)
          filter_rules = [<list of filter rules>],
          filter_id = <The ID of an existing filter>,
          order = [{attribute: <resource attribute>, sort: <'asc' or 'desc'>}],
          pagination = {'size': <size>, 'offset': <offset>},
          all_tenants = <True or False>,
          get_all_results = <True or False>
        }
        """
        request_schema = {
            'include': {'optional': True, 'type': list},
            'filter_rules': {'optional': True, 'type': list},
            'filter_id': {'optional': True, 'type': text_type},
            'order': {'optional': True, 'type': list},
            'pagination': {'optional': True, 'type': dict},
            'all_tenants': {'optional': True, 'type': bool},
            'get_all_results': {'optional': True, 'type': bool}
        }
        request_dict = rest_utils.get_json_and_verify_params(request_schema)

        if _include and {'labels', 'deployment_groups'}.intersection(_include):
            _include = None
        filter_rules = _get_filter_rules(request_dict, resource_model)
        order_dict = _get_order_dict(request_dict, resource_model)
        pagination = _get_pagination(request_dict)

        result = get_storage_manager().list(
            resource_model,
            include=_include,
            filter_rules=filter_rules,
            pagination=pagination,
            sort=order_dict,
            all_tenants=request_dict.get('all_tenants'),
            get_all_results=request_dict.get('get_all_results')
        )

        return ListResponse(items=result.items, metadata=result.metadata)


def _get_filter_rules(request_dict, resource_model):
    filter_rules = []
    filter_id = request_dict.get('filter_id')
    raw_filter_rules = request_dict.get('filter_rules')

    if raw_filter_rules:
        filter_rules = create_filter_rules_list(raw_filter_rules,
                                                resource_model)
    if filter_id:
        rest_utils.validate_inputs({'filter_id': filter_id})
        filter_elem = get_storage_manager().get(models.Filter, filter_id)
        filter_rules.extend(filter_elem.value)

    return filter_rules


def _get_pagination(request_dict):
    pagination_dict = request_dict.get('pagination')
    if pagination_dict is None:
        return

    err_msg = "The `pagination` value must be a dictionary of the form " \
              "{'size': <a positive integer>, 'offset': <a positive integer>}"
    if pagination_dict.keys() != {'size', 'offset'}:
        raise manager_exceptions.BadParametersError(err_msg)
    size, offset = pagination_dict['size'], pagination_dict['offset']
    if not isinstance(size, int) or not isinstance(offset, int):
        raise manager_exceptions.BadParametersError(err_msg)
    if pagination_dict['size'] <= 0 or pagination_dict['offset'] <= 0:
        raise manager_exceptions.BadParametersError(err_msg)

    return pagination_dict


def _get_order_dict(request_dict, resource_model):
    order_list = request_dict.get('order')
    if order_list is None:
        return

    err_msg = "The `sort` value must be a list of dictionaries of the form " \
              "{'attribute': <resource attribute>, 'sort':<'asc' or 'desc'>}"
    order_dict = OrderedDict()
    for order in order_list:
        if order.keys() != {'attribute', 'sort'}:
            raise manager_exceptions.BadParametersError(err_msg)
        order_by = order['sort']
        if order_by not in ('asc', 'desc'):
            raise manager_exceptions.BadParametersError(err_msg)
        order_dict[order['attribute']] = order_by

    if any(attr not in resource_model.resource_fields for attr in order_dict):
        raise manager_exceptions.BadParametersError(err_msg)

    return order_dict


class DeploymentsSearches(ResourceSearches):
    @authorize('deployment_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Deployment)
    def post(self, _include=None):
        """List Deployments"""
        return super().post(models.Deployment, _include)


class BlueprintsSearches(ResourceSearches):
    @authorize('blueprint_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Blueprint)
    def post(self, _include=None):
        """List Blueprints"""
        return super().post(models.Blueprint, _include)

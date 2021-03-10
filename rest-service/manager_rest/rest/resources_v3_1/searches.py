from flask import request

from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager

from ..responses_v2 import ListResponse
from .. import rest_decorators, rest_utils
from ..filters_utils import (create_filter_rules_list,
                             FilterRule,
                             get_filter_rules_from_filter_id)


class ResourceSearches(SecuredResource):
    def post(self, resource_model, _include, filters, pagination, sort,
             all_tenants, filter_id, **kwargs):
        """List resource items"""
        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        request_schema = {'filter_rules': {'optional': False, 'type': list}}
        request_dict = rest_utils.get_json_and_verify_params(request_schema)

        filter_rules = get_filter_rules(request_dict['filter_rules'],
                                        resource_model, filter_id)

        result = get_storage_manager().list(
            resource_model,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants,
            get_all_results=get_all_results,
            filter_rules=filter_rules
        )

        return ListResponse(items=result.items, metadata=result.metadata)


def get_filter_rules(raw_filter_rules, resource_model, filter_id):
    filter_rules = create_filter_rules_list(raw_filter_rules, resource_model)
    if filter_id:
        existing_filter_rules = get_filter_rules_from_filter_id(filter_id)
        for existing_filter_rule in existing_filter_rules:
            filter_rule_elem = FilterRule(existing_filter_rule['key'],
                                          existing_filter_rule['values'],
                                          existing_filter_rule['operator'],
                                          existing_filter_rule['type'])
            if filter_rule_elem in filter_rules:
                continue
            filter_rules.append(filter_rule_elem)

    return filter_rules


class DeploymentsSearches(ResourceSearches):
    @authorize('deployment_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Deployment)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Deployment)
    @rest_decorators.all_tenants
    @rest_decorators.filter_id
    def post(self, _include=None, pagination=None, sort=None,
             all_tenants=None, filter_id=None, **kwargs):
        """List Deployments using filter rules"""
        filters, _include = rest_utils.modify_deployments_list_args({},
                                                                    _include)
        return super().post(models.Deployment, _include, filters, pagination,
                            sort, all_tenants, filter_id, **kwargs)


class BlueprintsSearches(ResourceSearches):
    @authorize('blueprint_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Blueprint)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Blueprint)
    @rest_decorators.all_tenants
    @rest_decorators.filter_id
    def post(self, _include=None, pagination=None, sort=None,
             all_tenants=None, filter_id=None, **kwargs):
        """List Blueprints using filter rules"""
        filters, _include = rest_utils.modify_blueprints_list_args({},
                                                                   _include)
        return super().post(models.Blueprint, _include, filters, pagination,
                            sort, all_tenants, filter_id, **kwargs)

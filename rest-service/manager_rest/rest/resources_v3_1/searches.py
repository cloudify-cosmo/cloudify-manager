from flask import request
from flask_restful_swagger import swagger

from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.constants import (ATTRS_OPERATORS,
                                    FILTER_RULE_TYPES,
                                    LABELS_OPERATORS)

from ..responses_v2 import ListResponse
from .. import rest_decorators, rest_utils
from ..filters_utils import (create_filter_rules_list,
                             FilterRule,
                             get_filter_rules_from_filter_id)

from .workflows import workflows_list_response


def _get_swagger_searches_parameters():
    return [
        {
            'in': 'query',
            'name': '_include',
            'type': 'string',
            'required': 'false'
        },
        {
            'in': 'query',
            'name': '_size',
            'type': 'integer',
            'required': 'false'
        },
        {
            'in': 'query',
            'name': '_offset',
            'type': 'integer',
            'required': 'false'
        },
        {
            'in': 'query',
            'name': '_sort',
            'type': 'string',
            'required': 'false'
        },
        {
            'in': 'query',
            'name': '_all_tenants',
            'type': 'boolean',
            'required': 'false'
        },
        {
            'in': 'query',
            'name': '_get_all_results',
            'type': 'boolean',
            'required': 'false'
        },
        {
            'in': 'query',
            'name': '_filter_id',
            'type': 'string',
            'required': 'false'
        },
    ]


def _swagger_searches_docs(resource_model, resource_name):
    return {
        'responseClass': f'List[{resource_model.__name__}]',
        'nickname': 'list',
        'notes': f'Returns a filtered list of existing {resource_name}, '
                 f'based on the provided filter rules.',
        'parameters': _get_swagger_searches_parameters(),
        'allowed_filter_rules_attrs': resource_model.allowed_filter_attrs,
        'filter_rules_attributes_operators': ATTRS_OPERATORS,
        'filter_rules_labels_operators': LABELS_OPERATORS,
        'filter_rules_types': FILTER_RULE_TYPES
    }


class ResourceSearches(SecuredResource):
    def post(self, resource_model, filters_model, _include, filters,
             pagination, sort, all_tenants, search, filter_id, **kwargs):
        """List resource items"""
        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        request_schema = {'filter_rules': {'optional': False, 'type': list}}
        request_dict = rest_utils.get_json_and_verify_params(request_schema)

        filter_rules = get_filter_rules(request_dict['filter_rules'],
                                        resource_model, filters_model,
                                        filter_id)

        result = get_storage_manager().list(
            resource_model,
            include=_include,
            filters=filters,
            substr_filters=search,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants,
            get_all_results=get_all_results,
            filter_rules=filter_rules
        )

        return ListResponse(items=result.items, metadata=result.metadata)


def get_filter_rules(raw_filter_rules,
                     resource_model,
                     filters_model,
                     filter_id):
    filter_rules = create_filter_rules_list(raw_filter_rules, resource_model)
    if filter_id:
        existing_filter_rules = get_filter_rules_from_filter_id(
            filter_id, filters_model)
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
    @swagger.operation(**_swagger_searches_docs(models.Deployment,
                                                'deployments'))
    @authorize('deployment_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Deployment)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Deployment)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    @rest_decorators.filter_id
    def post(self, _include=None, pagination=None, sort=None,
             all_tenants=None, search=None, filter_id=None, **kwargs):
        """List deployments using filter rules"""
        filters, _include = rest_utils.modify_deployments_list_args({},
                                                                    _include)
        return super().post(models.Deployment, models.DeploymentsFilter,
                            _include, filters, pagination, sort, all_tenants,
                            search, filter_id, **kwargs)


class BlueprintsSearches(ResourceSearches):
    @swagger.operation(**_swagger_searches_docs(models.Blueprint,
                                                'blueprints'))
    @authorize('blueprint_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Blueprint)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Blueprint)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    @rest_decorators.filter_id
    def post(self, _include=None, pagination=None, sort=None,
             all_tenants=None, search=None, filter_id=None, **kwargs):
        """List blueprints using filter rules"""
        filters, _include = rest_utils.modify_blueprints_list_args({},
                                                                   _include)
        return super().post(models.Blueprint, models.BlueprintsFilter,
                            _include, filters, pagination, sort, all_tenants,
                            search, filter_id, **kwargs)


class WorkflowsSearches(ResourceSearches):
    @swagger.operation(
        responseClass='List[dict]',
        nickname='list',
        notes='Returns a filtered list of existing workflows, '
              'based on the provided filter rules.',
        parameters=_get_swagger_searches_parameters(),
        allowed_filter_rules_attrs=models.Deployment.allowed_filter_attrs,
        filter_rules_attributes_operators=ATTRS_OPERATORS,
        filter_rules_labels_operators=LABELS_OPERATORS,
        filter_rules_types=FILTER_RULE_TYPES)
    @authorize('deployment_list', allow_all_tenants=True)
    @rest_decorators.marshal_list_response
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    @rest_decorators.filter_id
    def post(self, all_tenants=None, search=None, filter_id=None, **kwargs):
        """List workflows using filter rules"""
        _include = ['id', 'workflows']
        filters, _include = rest_utils.modify_deployments_list_args({},
                                                                    _include)

        result = super().post(models.Deployment, models.DeploymentsFilter,
                              _include, filters, None, None, all_tenants,
                              search, filter_id, **kwargs)

        return workflows_list_response(result)

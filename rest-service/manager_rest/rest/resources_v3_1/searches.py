from collections import defaultdict

from flask import request
from flask_restful.reqparse import Argument
from flask_restful_swagger import swagger

from manager_rest import manager_exceptions
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.constants import (ATTRS_OPERATORS,
                                    FILTER_RULE_TYPES,
                                    LABELS_OPERATORS)

from ..responses_v2 import ListResponse
from ..search_utils import get_filter_rules
from .. import rest_decorators, rest_utils, responses_v3

from .workflows import workflows_list_response

DEPLOYMENT_SEARCHES_MAP = {'_search': 'id', '_search_name': 'display_name'}


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
        request_schema = {'filter_rules': {'optional': True, 'type': list},
                          'constraints': {'optional': True, 'type': dict}}
        request_dict = rest_utils.get_json_and_verify_params(request_schema)

        filter_rules = get_filter_rules(resource_model, filters_model,
                                        filter_id,
                                        request_dict.get('filter_rules'),
                                        request_dict.get('constraints'))

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


class DeploymentsSearches(ResourceSearches):
    @swagger.operation(**_swagger_searches_docs(models.Deployment,
                                                'deployments'))
    @authorize('deployment_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Deployment)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Deployment)
    @rest_decorators.all_tenants
    @rest_decorators.search_multiple_parameters(DEPLOYMENT_SEARCHES_MAP)
    @rest_decorators.filter_id
    def post(self, _include=None, pagination=None, sort=None,
             all_tenants=None, search=None, filter_id=None, **kwargs):
        """List deployments using filter rules or DSL constraints"""
        filters = rest_utils.deployment_group_id_filter()
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
        """List blueprints using filter rules or DSL constraints"""
        filters = {'is_hidden': False}
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
        filters = rest_utils.deployment_group_id_filter()
        result = super().post(models.Deployment, models.DeploymentsFilter,
                              _include, filters, None, None, all_tenants,
                              search, filter_id, **kwargs)

        return workflows_list_response(result)


class NodeInstancesSearches(ResourceSearches):
    @swagger.operation(**_swagger_searches_docs(models.NodeInstance,
                                                'node_instances'))
    @authorize('node_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.NodeInstance)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.NodeInstance)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    @rest_decorators.filter_id
    def post(self, _include=None, pagination=None, sort=None,
             all_tenants=None, search=None, filter_id=None, **kwargs):
        """List NodeInstances using filter rules"""
        return super().post(models.NodeInstance, None,
                            _include, {}, pagination, sort, all_tenants,
                            search, filter_id, **kwargs)


class CapabilitiesSearches(ResourceSearches):
    @swagger.operation(
        responseClass=f'List[{responses_v3.DeploymentCapabilities.__name__}]',
        nickname="list",
        notes="Returns a filtered list of existing capabilities of a specific "
              "deployment.",
        parameters=[
            {
                'in': 'query',
                'name': '_deployment_id',
                'type': 'string',
                'required': 'true'
            },
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
        ]
    )
    @authorize('deployment_capabilities', allow_all_tenants=True)
    @rest_decorators.marshal_with(responses_v3.DeploymentCapabilities)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
    def post(self, search=None, _include=None,
             pagination=None, all_tenants=None, **kwargs):
        """List capabilities using DSL constraints"""
        args = rest_utils.get_args_and_verify_arguments([
            Argument('_deployment_id', required=True),
            Argument('_search', required=False),
        ])
        deployment_id = args._deployment_id
        search = args._search
        if not deployment_id:
            raise manager_exceptions.BadParametersError(
                "You should provide a valid '_deployment_id' when searching "
                " for capabilities.")

        request_schema = {'constraints': {'optional': False, 'type': dict}}
        request_dict = rest_utils.get_json_and_verify_params(request_schema)
        constraints = request_dict['constraints']

        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )

        deployments = get_storage_manager().list(
            models.Deployment,
            include=_include,
            substr_filters={'id': deployment_id},
            pagination=pagination,
            all_tenants=all_tenants,
            get_all_results=get_all_results,
        )
        metadata = deployments.metadata

        dep_capabilities = defaultdict(lambda: [])
        for dep in deployments:
            if not dep.capabilities:
                continue
            for key, capability in dep.capabilities.items():
                if capability_matches(key, capability, constraints, search):
                    dep_capabilities[dep.id].append({key: capability})

        metadata['filtered'] = \
            metadata['pagination']['total'] - len(dep_capabilities)
        metadata['pagination']['total'] = len(dep_capabilities)
        return ListResponse(
            items=[{'deployment_id': k, 'capabilities': v}
                   for k, v in dep_capabilities.items()],
            metadata=metadata
        )


def capability_matches(capability_key, capability, constraints, search_value):
    for constraint, specification in constraints.items():
        if constraint == 'capability_key_specs':
            for operator, value in specification.items():
                if operator == 'contains':
                    if value not in capability_key:
                        return False
                elif operator == 'starts_with':
                    if not capability_key.startswith(str(value)):
                        return False
                elif operator == 'ends_with':
                    if not capability_key.endswith(str(value)):
                        return False
                elif operator == 'equals_to':
                    if capability_key != str(value):
                        return False
                else:
                    raise NotImplementedError('Unknown capabilities name '
                                              f'pattern operator: {operator}')
        elif constraint == 'valid_values':
            if capability['value'] not in specification:
                return False

    if search_value:
        return capability['value'] == search_value

    return True

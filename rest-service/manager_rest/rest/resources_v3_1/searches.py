from collections import defaultdict

from flask import request
from flask_restful.reqparse import Argument

from dsl_parser.utils import get_function

from manager_rest import manager_exceptions
from manager_rest.rest import swagger
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.constants import (ATTRS_OPERATORS,
                                    FILTER_RULE_TYPES,
                                    LABELS_OPERATORS)
from manager_rest.dsl_functions import evaluate_intrinsic_functions

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
        constraints = kwargs.get('constraints') if 'constraints' in kwargs \
            else request_dict.get('constraints')
        resource_field = kwargs.get('resource_field', 'id')
        sm = get_storage_manager()
        filter_rules = get_filter_rules(sm,
                                        resource_model,
                                        resource_field,
                                        filters_model,
                                        filter_id,
                                        request_dict.get('filter_rules'),
                                        constraints)

        result = sm.list(
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
                            search, filter_id, resource_field='display_name',
                            **kwargs)


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


class NodesSearches(ResourceSearches):
    @swagger.operation(**_swagger_searches_docs(models.Node, 'nodes'))
    @authorize('node_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Node)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Node)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def post(self, _include=None, pagination=None, sort=None,
             all_tenants=None, search=None, **kwargs):
        """List Nodes using filter rules or DSL constraints"""
        blueprint_id, deployment_id, constraints = \
            retrieve_constraints(id_required=True)

        if blueprint_id:
            sm = get_storage_manager()
            blueprint = sm.get(models.Blueprint, blueprint_id,
                               all_tenants=all_tenants)
            return self.nodes_from_plan(blueprint, search, constraints)

        filters = {'deployment_id': deployment_id}
        rf = 'operation_name' if 'operation_name_specs' in constraints \
            else 'id'
        return super().post(models.Node, None, _include, filters, pagination,
                            sort, all_tenants, search, None,
                            resource_field=rf, **kwargs)

    @staticmethod
    def nodes_from_plan(blueprint, search_value, constraints):
        results, filtered = [], 0
        for node in blueprint.plan['nodes']:
            if node_matches(node, search_value, **constraints):
                results.append(node)
            else:
                filtered += 1
        return ListResponse(
            items=results,
            metadata={
                'filtered': filtered,
                'pagination': {
                    'offset': 0,
                    'size': len(results),
                    'total': len(results) + filtered,
                }
            }
        )


class NodeTypesSearches(ResourceSearches):
    @swagger.operation(**_swagger_searches_docs(models.Node, 'nodes'))
    @authorize('node_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.Node)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Node)
    @rest_decorators.all_tenants
    @rest_decorators.search('type')
    def post(self, _include=None, pagination=None, sort=None,
             all_tenants=None, search=None, **kwargs):
        """List Nodes using filter rules or DSL constraints"""
        blueprint_id, deployment_id, constraints = \
            retrieve_constraints(id_required=True)
        if 'name_pattern' in constraints:
            constraints['type_specs'] = constraints.pop('name_pattern')

        if blueprint_id:
            sm = get_storage_manager()
            blueprint = sm.get(models.Blueprint, blueprint_id,
                               all_tenants=all_tenants)
            return self.node_types_from_plan(blueprint,
                                             search['type'],
                                             constraints)

        if 'valid_values' in constraints:
            constraints['valid_values'] = extend_node_type_valid_values(
                deployment_id, constraints['valid_values'])
        filters = {'deployment_id': deployment_id}
        return super().post(models.Node, None, _include, filters, pagination,
                            sort, all_tenants, search, None,
                            constraints=constraints,
                            resource_field='type', **kwargs)

    @staticmethod
    def node_types_from_plan(blueprint, search_value, constraints):
        results, filtered = [], 0
        for node in blueprint.plan['nodes']:
            if node_type_matches(node, search_value, **constraints):
                results.append(node)
            else:
                filtered += 1
        return ListResponse(
            items=results,
            metadata={
                'filtered': filtered,
                'pagination': {
                    'offset': 0,
                    'size': len(results),
                    'total': len(results) + filtered,
                }
            }
        )


class NodeInstancesSearches(ResourceSearches):
    @swagger.operation(**_swagger_searches_docs(models.NodeInstance,
                                                'node_instances'))
    @authorize('node_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.NodeInstance)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.NodeInstance)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def post(self, _include=None, pagination=None, sort=None,
             all_tenants=None, search=None, **kwargs):
        """List NodeInstances using filter rules"""
        _, deployment_id, constraints = retrieve_constraints()
        if 'name_pattern' in constraints:
            constraints['id_specs'] = constraints.pop('name_pattern')
        args = rest_utils.get_args_and_verify_arguments([
            Argument('node_id', required=False),
        ])
        node_id = args.get('node_id')
        filters = {}
        if deployment_id:
            filters['deployment_id'] = deployment_id
        if node_id:
            filters['node_id'] = node_id
        return super().post(models.NodeInstance, None, _include, filters,
                            pagination, sort, all_tenants, search, None,
                            constraints=constraints,
                            resource_field='id', **kwargs)


class SecretsSearches(ResourceSearches):
    @swagger.operation(**_swagger_searches_docs(models.Secret,
                                                'secrets'))
    @authorize('secret_list', allow_all_tenants=False)
    @rest_decorators.marshal_with(models.Secret)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Secret)
    @rest_decorators.search('id')
    def post(self, _include=None, pagination=None, sort=None,
             search=None, **kwargs):
        """List secrets using filter rules or DSL constraints"""
        return super().post(models.Secret, None, _include, {}, pagination,
                            sort, False, search, None,
                            resource_field='key', **kwargs)


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
        _, deployment_id, constraints = retrieve_constraints(id_required=True)
        if 'name_pattern' in constraints:
            constraints['capability_key_specs'] = \
                constraints.pop('name_pattern')
        args = rest_utils.get_args_and_verify_arguments([
            Argument('_search', required=False),
        ])
        search = args._search

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
            for key, raw_capability in dep.capabilities.items():
                if get_function(raw_capability.get('value')):
                    capability = evaluate_intrinsic_functions(
                        raw_capability, dep.id)
                else:
                    capability = raw_capability
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


class ScalingGroupsSearches(ResourceSearches):
    @swagger.operation(
        responseClass=f'List[{responses_v3.ScalingGroupResponse.__name__}]',
        nickname="list",
        notes="Returns a filtered list of existing scaling groups "
              "of a specific deployment.",
        parameters=[
            {
                'in': 'query',
                'name': '_deployment_id',
                'type': 'string',
                'required': 'true'
            },
            {
                'in': 'query',
                'name': '_search',
                'type': 'string',
                'required': 'false'
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
    @authorize('deployment_get', allow_all_tenants=True)
    @rest_decorators.marshal_with(responses_v3.ScalingGroupResponse)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
    def post(self, _include=None, pagination=None, all_tenants=None, **kwargs):
        """List scaling groups using DSL constraints"""
        blueprint_id, deployment_id, constraints = \
            retrieve_constraints(id_required=True)
        if 'name_pattern' in constraints:
            constraints['scaling_group_name_specs'] = \
                constraints.pop('name_pattern')
        args = rest_utils.get_args_and_verify_arguments([
            Argument('_search', required=False),
        ])
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

        results, filtered_out = [], 0
        for dep in deployments:
            if not dep.scaling_groups:
                continue
            for name, scaling_group in dep.scaling_groups.items():
                if scaling_group_name_matches(
                        name, constraints, args.get('_search')):
                    results.append({
                        'deployment_id': dep.id,
                        'name': name,
                        'members': scaling_group.get('members'),
                        'properties': scaling_group.get('properties'),
                    })
                else:
                    filtered_out += 1

        metadata['filtered'] = filtered_out
        metadata['pagination']['total'] = len(results) + filtered_out
        return ListResponse(
            items=results,
            metadata=metadata
        )


def retrieve_constraints(id_required=False):
    args = rest_utils.get_args_and_verify_arguments([
        Argument('deployment_id', required=False),
        Argument('blueprint_id', required=False),
    ])
    request_dict = rest_utils.get_json_and_verify_params(
        {'constraints': {'optional': True, 'type': dict}})
    constraints = request_dict.get('constraints', {})
    if args.get('deployment_id') and 'deployment_id' in constraints:
        raise manager_exceptions.BadParametersError(
            "You should provide either a valid 'deployment_id' parameter "
            "or have a 'deployment_id' key in the constraints, not both.")
    if args.get('blueprint_id') and 'blueprint_id' in constraints:
        raise manager_exceptions.BadParametersError(
            "You should provide either a valid 'blueprint_id' parameter "
            "or have a 'blueprint_id' key in the constraints, not both.")
    deployment_id = args.get('deployment_id') \
        or constraints.get('deployment_id')
    blueprint_id = args.get('blueprint_id') \
        or constraints.get('blueprint_id')
    if (constraints or id_required) \
            and not deployment_id and not blueprint_id:
        raise manager_exceptions.BadParametersError(
            "Please provide a valid 'blueprint_id' or 'deployment_id' "
            "parameter or have a relevant key in the constraints.")
    if blueprint_id and deployment_id:
        raise manager_exceptions.BadParametersError(
            "You should provide either 'blueprint_id' or 'deployment_id' "
            "constraints, not both.")
    return blueprint_id, deployment_id, constraints


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


def scaling_group_name_matches(scaling_group_name, constraints, search_value):
    for constraint, specification in constraints.items():
        if constraint == 'scaling_group_name_specs':
            for operator, value in specification.items():
                if operator == 'contains':
                    if value not in scaling_group_name:
                        return False
                elif operator == 'starts_with':
                    if not scaling_group_name.startswith(str(value)):
                        return False
                elif operator == 'ends_with':
                    if not scaling_group_name.endswith(str(value)):
                        return False
                elif operator == 'equals_to':
                    if scaling_group_name != str(value):
                        return False
                else:
                    raise NotImplementedError('Unknown scaling group name '
                                              f'pattern operator: {operator}')
        elif constraint == 'valid_values':
            if scaling_group_name not in specification:
                return False

    if search_value:
        return scaling_group_name == search_value

    return True


def extend_node_type_valid_values(deployment_id, valid_values):
    """Extend the list of valid node types based on the type hierarchy.
    Include also ancestors of the types listed as valid_values."""
    sm = get_storage_manager()
    nodes = sm.list(
        models.Node,
        filters={'deployment_id': deployment_id},
        include='id,type,type_hierarchy',
        get_all_results=True)
    valid_values = set(valid_values)
    results = valid_values.copy()
    for node in nodes:
        for value in valid_values:
            if value not in node.type_hierarchy:
                continue
            th = node.type_hierarchy
            results.update(th[th.index(value):])
    return list(results)


def node_matches(node, search_value, valid_values=None,
                 id_specs=None, operation_name_specs=None):
    """Verify if node matches the constraints. If id_specs is set node['id']
    will be tested, if operation_name_specs - these will be node['operation']
    keys (i.e. operation names).

    :param node: a node to test.
    :param search_value: value of an input/parameter, if provided, must match
                         node['id'] or one of the operation names.
    :param valid_values: a list of allowed values either.
    :param id_specs: a dictionary describing a name_pattern constraint
                     for node['id'].
    :param operation_name_specs: a dictionary describing a name_pattern
                                 constraint for one of the operation names.
    :return: `True` if `node` matches the constraints provided with the other
             parameters.
    """
    if id_specs:
        for operator, value in id_specs.items():
            match operator:
                case 'contains':
                    if value not in node['id']:
                        return False
                case 'starts_with':
                    if not node['id'].startswith(str(value)):
                        return False
                case 'ends_with':
                    if not node['id'].endswith(str(value)):
                        return False
                case 'equals_to':
                    if node['id'] != str(value):
                        return False
                case _:
                    raise NotImplementedError('Unknown operation name '
                                              f'pattern operator: {operator}')
    if valid_values:
        if id_specs and node['id'] not in valid_values:
            return False
        if operation_name_specs and all(op not in valid_values
                                        for op in node['operations'].keys()):
            return False
    if search_value:
        if id_specs:
            return node['id'] == search_value
        if operation_name_specs:
            return any(op == search_value for op in node['operations'].keys())

    return True


def node_type_matches(node, search_value, valid_values=None, type_specs=None):
    """Verify if node_type matches the constraints.

    :param node: node to test (whole dict).
    :param search_value: value of an input/parameter of type node_type,
                         if provided, must exactly match `node_type`.
    :param valid_values: a list of allowed values for the `node_type`.
    :param type_specs: a dictionary describing a name_pattern constraint
                       for `node_type`.
    :return: `True` if `node_type` matches the constraints provided with
             the other three parameters.
    """
    node_type = node['type']
    if type_specs:
        for operator, value in type_specs.items():
            match operator:
                case 'contains':
                    if value not in node_type:
                        return False
                case 'starts_with':
                    if not node_type.startswith(str(value)):
                        return False
                case 'ends_with':
                    if not node_type.endswith(str(value)):
                        return False
                case 'equals_to':
                    if node_type != str(value):
                        return False
                case _:
                    raise NotImplementedError('Unknown operation name '
                                              f'pattern operator: {operator}')
    if valid_values:
        valid_values_with_children = set(valid_values)
        for value in valid_values:
            if value not in valid_values_with_children:
                continue
            th = node['type_hierarchy']
            if value in th:
                valid_values_with_children.update(th[th.index(value):])
        if node_type not in valid_values_with_children:
            return False
    if search_value:
        return node_type == search_value

    return True

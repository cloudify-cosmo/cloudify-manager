from flask import request

from cloudify.models_states import VisibilityState

from manager_rest import manager_exceptions
from manager_rest.security import SecuredResource
from manager_rest.utils import get_formatted_timestamp
from manager_rest.rest import rest_decorators, rest_utils
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest.filters_utils import create_filter_rules_list


class BlueprintsFilters(SecuredResource):
    @authorize('filters_list')
    @rest_decorators.marshal_with(models.Filter)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Filter)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, _include=None, pagination=None, sort=None,
            all_tenants=None, search=None):
        """List blueprints filters"""

        return list_resource_filters('blueprints', _include, pagination, sort,
                                     all_tenants, search)


class DeploymentsFilters(SecuredResource):
    @authorize('filters_list')
    @rest_decorators.marshal_with(models.Filter)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Filter)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, _include=None, pagination=None, sort=None,
            all_tenants=None, search=None):
        """List deployments filters"""

        return list_resource_filters('deployments', _include, pagination, sort,
                                     all_tenants, search)


def list_resource_filters(filtered_resource, _include=None, pagination=None,
                          sort=None, all_tenants=None, search=None):
    get_all_results = rest_utils.verify_and_convert_bool(
        '_get_all_results',
        request.args.get('_get_all_results', False)
    )
    result = get_storage_manager().list(
        models.Filter,
        include=_include,
        substr_filters=search,
        pagination=pagination,
        sort=sort,
        all_tenants=all_tenants,
        get_all_results=get_all_results,
        filters={'filtered_resource': filtered_resource}
    )

    return result


class FiltersId(SecuredResource):
    def put(self, filter_id, filtered_resource):
        """Create a filter"""
        rest_utils.validate_inputs({'filter_id': filter_id})
        request_dict = rest_utils.get_json_and_verify_params(
            {'filter_rules': {'type': list}})
        filter_rules = create_filter_rules_list(request_dict['filter_rules'],
                                                filtered_resource)
        visibility = rest_utils.get_visibility_parameter(
            optional=True, valid_values=VisibilityState.STATES)

        now = get_formatted_timestamp()
        new_filter = models.Filter(
            id=filter_id,
            value=filter_rules,
            filtered_resource=filtered_resource,
            created_at=now,
            updated_at=now,
            visibility=visibility
        )

        return get_storage_manager().put(new_filter)

    @authorize('filters_get')
    @rest_decorators.marshal_with(models.Filter)
    def get(self, filter_id, _include=None):
        """
        Get a filter by ID
        """
        rest_utils.validate_inputs({'filter_id': filter_id})
        return get_storage_manager().get(
            models.Filter, filter_id, include=_include)

    @authorize('filters_delete')
    def delete(self, filter_id):
        """
        Delete a filter by ID
        """
        rest_utils.validate_inputs({'filter_id': filter_id})
        storage_manager = get_storage_manager()
        filter_elem = storage_manager.get(models.Filter, filter_id)
        storage_manager.delete(filter_elem, validate_global=True)
        return None, 204

    def patch(self, filter_id, filtered_resource):
        """Update a filter by its ID

        This function updates the filter rules and visibility
        """
        rest_utils.validate_inputs({'filter_id': filter_id})
        if not request.json:
            raise manager_exceptions.IllegalActionError(
                'Update a filter request must include at least one parameter '
                'to update')

        request_dict = rest_utils.get_json_and_verify_params(
            {'filter_rules': {'type': list, 'optional': True}})

        filter_rules = request_dict.get('filter_rules')
        visibility = rest_utils.get_visibility_parameter(
            optional=True, valid_values=VisibilityState.STATES)

        storage_manager = get_storage_manager()
        filter_elem = storage_manager.get(models.Filter, filter_id)
        if visibility:
            get_resource_manager().validate_visibility_value(
                models.Filter, filter_elem, visibility)
            filter_elem.visibility = visibility
        if filter_rules:
            filter_elem.value = create_filter_rules_list(filter_rules,
                                                         filtered_resource)
        filter_elem.updated_at = get_formatted_timestamp()

        return storage_manager.update(filter_elem)


class BlueprintsFiltersId(FiltersId):
    @authorize('filters_create')
    @rest_decorators.marshal_with(models.Filter)
    def put(self, filter_id):
        return super().put(filter_id, 'blueprints')

    @authorize('filters_update')
    @rest_decorators.marshal_with(models.Filter)
    def patch(self, filter_id):
        return super().patch(filter_id, 'blueprints')


class DeploymentsFiltersId(FiltersId):
    @authorize('filters_create')
    @rest_decorators.marshal_with(models.Filter)
    def put(self, filter_id):
        return super().put(filter_id, 'deployments')

    @authorize('filters_update')
    @rest_decorators.marshal_with(models.Filter)
    def patch(self, filter_id):
        return super().patch(filter_id, 'deployments')

from flask import request

from cloudify.models_states import VisibilityState

from manager_rest import manager_exceptions
from manager_rest.security import SecuredResource
from manager_rest.constants import RESERVED_PREFIX
from manager_rest.utils import get_formatted_timestamp
from manager_rest.rest import rest_decorators, rest_utils
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
from manager_rest.storage import models, get_storage_manager
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest.filters_utils import create_filter_rules_list


class BlueprintsFilters(SecuredResource):
    @authorize('filter_list')
    @rest_decorators.marshal_with(models.BlueprintsFilter)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.BlueprintsFilter)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, _include=None, pagination=None, sort=None,
            all_tenants=None, search=None):
        """List blueprints filters"""

        return list_resource_filters(models.BlueprintsFilter, _include,
                                     pagination, sort, all_tenants, search)


class DeploymentsFilters(SecuredResource):
    @authorize('filter_list')
    @rest_decorators.marshal_with(models.DeploymentsFilter)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.DeploymentsFilter)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, _include=None, pagination=None, sort=None,
            all_tenants=None, search=None):
        """List deployments filters"""

        return list_resource_filters(models.DeploymentsFilter, _include,
                                     pagination, sort, all_tenants, search)


def list_resource_filters(filters_model, _include=None, pagination=None,
                          sort=None, all_tenants=None, search=None):
    get_all_results = rest_utils.verify_and_convert_bool(
        '_get_all_results',
        request.args.get('_get_all_results', False)
    )
    result = get_storage_manager().list(
        filters_model,
        include=_include,
        substr_filters=search,
        pagination=pagination,
        sort=sort,
        all_tenants=all_tenants,
        get_all_results=get_all_results,
    )

    return result


class FiltersId(SecuredResource):
    def put(self, filters_model, filter_id, filtered_resource):
        """Create a filter"""
        rest_utils.validate_inputs({'filter_id': filter_id})
        if filter_id.lower().startswith(RESERVED_PREFIX):
            raise manager_exceptions.BadParametersError(
                f'All filters with a `{RESERVED_PREFIX}` prefix are reserved '
                f'for internal use.')
        request_dict = rest_utils.get_json_and_verify_params(
            {'filter_rules': {'type': list}})
        filter_rules = create_filter_rules_list(request_dict['filter_rules'],
                                                filtered_resource)
        visibility = rest_utils.get_visibility_parameter(
            optional=True, valid_values=VisibilityState.STATES)

        created_at = creator = None
        if 'created_at' in request_dict:
            check_user_action_allowed('set_timestamp', None, True)
            created_at = rest_utils.parse_datetime_string(
                request_dict['created_at'])
        if 'creator' in request_dict:
            check_user_action_allowed('set_owner', None, True)
            creator = rest_utils.valid_user(request_dict['creator'])

        now = get_formatted_timestamp()
        new_filter = filters_model(
            id=filter_id,
            value=filter_rules,
            created_at=created_at or now,
            updated_at=now,
            visibility=visibility,
            creator=creator,
        )

        return get_storage_manager().put(new_filter)

    def get(self, filters_model, filter_id, _include=None):
        """
        Get a filter by ID
        """
        rest_utils.validate_inputs({'filter_id': filter_id})
        return get_storage_manager().get(
            filters_model, filter_id, include=_include)

    def delete(self, filters_model, filter_id):
        """
        Delete a filter by ID
        """
        rest_utils.validate_inputs({'filter_id': filter_id})
        storage_manager = get_storage_manager()
        filter_elem = storage_manager.get(filters_model, filter_id)
        _verify_not_a_system_filter(filter_elem, 'delete')
        storage_manager.delete(filter_elem, validate_global=True)
        return None, 204

    def patch(self, filters_model, filter_id, filtered_resource):
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
        filter_elem = storage_manager.get(filters_model, filter_id)
        _verify_not_a_system_filter(filter_elem, 'update')
        if visibility:
            get_resource_manager().validate_visibility_value(
                filters_model, filter_elem, visibility)
            filter_elem.visibility = visibility
        if filter_rules:
            new_filter_rules = create_filter_rules_list(filter_rules,
                                                        filtered_resource)
            new_attrs_filter_rules = _get_filter_rules_by_type(
                new_filter_rules, 'attribute')
            new_labels_filter_rules = _get_filter_rules_by_type(
                new_filter_rules, 'label')
            if new_attrs_filter_rules:
                if new_labels_filter_rules:  # Both need to be updated
                    filter_elem.value = new_filter_rules
                else:  # Only labels filter rules should be saved
                    filter_elem.value = (filter_elem.labels_filter_rules +
                                         new_filter_rules)

            elif new_labels_filter_rules:
                # Only attributes filter rules should be saved
                filter_elem.value = (filter_elem.attrs_filter_rules +
                                     new_filter_rules)

            else:  # Should not get here
                raise manager_exceptions.BadParametersError(
                    'Unknown filter rules type')

        filter_elem.updated_at = get_formatted_timestamp()

        return storage_manager.update(filter_elem)


def _get_filter_rules_by_type(filter_rules_list, filter_rule_type):
    return [filter_rule for filter_rule in
            filter_rules_list if filter_rule['type'] == filter_rule_type]


def _verify_not_a_system_filter(filter_elem, action):
    if filter_elem.is_system_filter:
        raise manager_exceptions.IllegalActionError(
            f'Cannot {action} a system filter')


class BlueprintsFiltersId(FiltersId):
    @authorize('filter_create')
    @rest_decorators.marshal_with(models.BlueprintsFilter)
    def put(self, filter_id):
        return super().put(models.BlueprintsFilter, filter_id,
                           models.Blueprint)

    @authorize('filter_get')
    @rest_decorators.marshal_with(models.BlueprintsFilter)
    def get(self, filter_id, _include=None):
        return super().get(models.BlueprintsFilter, filter_id, _include)

    @authorize('filter_update')
    @rest_decorators.marshal_with(models.BlueprintsFilter)
    def patch(self, filter_id):
        return super().patch(models.BlueprintsFilter, filter_id,
                             models.Blueprint)

    @authorize('filter_delete')
    def delete(self, filter_id):
        return super().delete(models.BlueprintsFilter, filter_id)


class DeploymentsFiltersId(FiltersId):
    @authorize('filter_create')
    @rest_decorators.marshal_with(models.DeploymentsFilter)
    def put(self, filter_id):
        return super().put(models.DeploymentsFilter, filter_id,
                           models.Deployment)

    @authorize('filter_get')
    @rest_decorators.marshal_with(models.DeploymentsFilter)
    def get(self, filter_id, _include=None):
        return super().get(models.DeploymentsFilter, filter_id, _include)

    @authorize('filter_update')
    @rest_decorators.marshal_with(models.DeploymentsFilter)
    def patch(self, filter_id):
        return super().patch(models.DeploymentsFilter, filter_id,
                             models.Deployment)

    @authorize('filter_delete')
    def delete(self, filter_id):
        return super().delete(models.DeploymentsFilter, filter_id)

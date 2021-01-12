from flask import request
from flask_security import current_user

from cloudify.models_states import VisibilityState

from manager_rest import manager_exceptions
from manager_rest.security import SecuredResource
from manager_rest.utils import get_formatted_timestamp
from manager_rest.rest import rest_decorators, rest_utils
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.resource_manager import get_resource_manager


class Filters(SecuredResource):
    @authorize('filters_list')
    @rest_decorators.marshal_with(models.Filter)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Filter)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, _include=None, pagination=None, sort=None,
            all_tenants=None, search=None):
        """List filters"""

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
            get_all_results=get_all_results
        )

        return result


class FiltersId(SecuredResource):
    @authorize('filters_create')
    @rest_decorators.marshal_with(models.Filter)
    def put(self, filter_id):
        """Create a filter

        Currently, this function only supports the creation of a labels filter
        """
        rest_utils.validate_inputs({'filter_id': filter_id})
        request_dict = rest_utils.get_json_and_verify_params(
            {'filter_rules': {'type': list}})
        labels_filters = rest_utils.parse_labels_filters(
            request_dict['filter_rules'])
        visibility = rest_utils.get_visibility_parameter(
            optional=True, valid_values=VisibilityState.STATES)

        now = get_formatted_timestamp()
        new_filter = models.Filter(
            id=filter_id,
            value={'labels': labels_filters},
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
        return get_storage_manager().get(
            models.Filter, filter_id, include=_include)

    @authorize('filters_delete')
    def delete(self, filter_id):
        """
        Delete a filter by ID
        """
        storage_manager = get_storage_manager()
        filter_elem = storage_manager.get(models.Filter, filter_id)
        _validate_filter_modification_permitted(filter_elem)
        storage_manager.delete(filter_elem, validate_global=True)
        return None, 204

    @authorize('filters_update')
    @rest_decorators.marshal_with(models.Filter)
    def patch(self, filter_id):
        """Update a filter by its ID

        This function updates the filter rules and visibility
        """
        if not request.json:
            raise manager_exceptions.IllegalActionError(
                'Update a filter request must include at least one parameter '
                'to update')

        request_dict = rest_utils.get_json_and_verify_params(
            {'filter_rules': {'type': list, 'optional': True}})

        labels_filters = request_dict.get('filter_rules')
        visibility = rest_utils.get_visibility_parameter(
            optional=True, valid_values=VisibilityState.STATES)

        storage_manager = get_storage_manager()
        filter_elem = storage_manager.get(models.Filter, filter_id)
        _validate_filter_modification_permitted(filter_elem)
        if visibility:
            get_resource_manager().validate_visibility_value(
                models.Filter, filter_elem, visibility)
            filter_elem.visibility = visibility
        if labels_filters:
            parsed_labels_filters = rest_utils.parse_labels_filters(
                labels_filters)
            filter_elem.value = {'labels': parsed_labels_filters}
        filter_elem.updated_at = get_formatted_timestamp()

        return storage_manager.update(filter_elem)


def _validate_filter_modification_permitted(filter_elem):
    if not (rest_utils.is_administrator(filter_elem.tenant) or
            filter_elem.created_by == current_user.username):
        raise manager_exceptions.ForbiddenError(
            'User `{0}` is not permitted to modify the filter `{1}`'.format(
                current_user.username, filter_elem.id)
        )

from flask import request

from cloudify.models_states import VisibilityState

from manager_rest.rest import rest_decorators, rest_utils
from manager_rest.security import SecuredResource
from manager_rest import utils, manager_exceptions
from manager_rest.security.authorization import (
    authorize,
    check_user_action_allowed,
)
from manager_rest.storage import models, get_storage_manager
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest.rest_utils import (validate_inputs,
                                          verify_and_convert_bool,
                                          get_visibility_parameter,
                                          get_json_and_verify_params)


class SitesName(SecuredResource):
    @rest_decorators.marshal_with(models.Site)
    @authorize('site_get')
    def get(self, name):
        """
        Get site by name
        """
        validate_inputs({'name': name})
        return get_storage_manager().get(models.Site, name)

    @rest_decorators.marshal_with(models.Site)
    @authorize('site_create')
    def put(self, name):
        """
        Create a new site
        """
        request_dict = self._validate_site_params(name)
        new_site = models.Site()
        new_site.id = name
        new_site.name = name
        new_site.latitude = request_dict.get('latitude')
        new_site.longitude = request_dict.get('longitude')
        new_site.visibility = (request_dict['visibility'] or
                               VisibilityState.TENANT)

        if 'created_at' in request_dict:
            check_user_action_allowed('set_timestamp')
            new_site.created_at = request_dict['created_at']
        else:
            new_site.created_at = utils.get_formatted_timestamp()

        if 'created_by' in request_dict:
            check_user_action_allowed('set_owner')
            new_site.creator = rest_utils.valid_user(
                request_dict['created_by'])
        return get_storage_manager().put(new_site)

    @rest_decorators.marshal_with(models.Site)
    @authorize('site_update')
    def post(self, name):
        """
        Update an existing site
        """
        request_dict = self._validate_site_params(name)
        storage_manager = get_storage_manager()
        self._validate_new_name(request_dict, storage_manager, name)
        site = storage_manager.get(models.Site, name)
        site.name = request_dict.get('new_name', site.name)
        site.id = request_dict.get('new_name', site.id)
        site.latitude = request_dict.get('latitude', site.latitude)
        site.longitude = request_dict.get('longitude', site.longitude)
        visibility = request_dict['visibility']
        if visibility:
            get_resource_manager().validate_visibility_value(site, visibility)
            site.visibility = visibility
        return storage_manager.update(site, validate_global=True)

    @authorize('site_delete')
    def delete(self, name):
        """
        Delete an existing site
        """
        storage_manager = get_storage_manager()
        site = storage_manager.get(models.Site, name)
        storage_manager.delete(site, validate_global=True)
        return None, 204

    def _validate_site_params(self, name):
        validate_inputs({'name': name})
        visibility = get_visibility_parameter(
            optional=True,
            valid_values=VisibilityState.STATES,
        )
        request_dict = get_json_and_verify_params({
            'location': {'type': str, 'optional': True},
            'new_name': {'type': str, 'optional': True}
        })
        request_dict['visibility'] = visibility
        self._validate_location(request_dict)
        return request_dict

    def _validate_location(self, request_dict):
        location = request_dict.get('location')
        if not location:
            if location == '':
                request_dict['latitude'] = None
                request_dict['longitude'] = None
            return

        # The location format is : "latitude,longitude"
        latitude, _, longitude = location.partition(',')

        # There is no comma separator
        if latitude == location:
            raise manager_exceptions.BadParametersError(
                'Invalid location `{0}`, the format is expected to be '
                '"latitude,longitude" such as "32.071072,34.787274"'
                .format(location)
            )

        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except ValueError:
            raise manager_exceptions.BadParametersError(
                "Invalid location `{0}`, the latitude and longitude are "
                "expected to be of type float".format(location)
            )

        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            raise manager_exceptions.BadParametersError(
                "Invalid location `{0}`. The latitude must be a number "
                "between -90 and 90 and the longitude between -180 and 180"
                .format(location)
            )

        request_dict['latitude'] = latitude
        request_dict['longitude'] = longitude

    def _validate_new_name(self, request_dict, storage_manager, current_name):
        new_name = request_dict.get('new_name')
        if not new_name or current_name == new_name:
            return

        validate_inputs({'new_name': new_name})
        if storage_manager.get(models.Site, new_name, fail_silently=True):
            raise manager_exceptions.ConflictError(
                'Invalid new name `{0}`, it already exists on {1} or '
                'with global visibility'.format(new_name, utils.current_tenant)
            )


class Sites(SecuredResource):
    @authorize('site_list')
    @rest_decorators.marshal_with(models.Site)
    @rest_decorators.create_filters(models.Site)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Site)
    @rest_decorators.all_tenants
    @rest_decorators.search('name')
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            all_tenants=None, search=None):
        """
        List sites
        """
        get_all_results = verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        return get_storage_manager().list(
            models.Site,
            include=_include,
            filters=filters,
            substr_filters=search,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants,
            get_all_results=get_all_results
        )

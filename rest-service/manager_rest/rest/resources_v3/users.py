from flask_security import current_user
from flask_security.utils import hash_password

from manager_rest import constants, config
from manager_rest.storage import models, user_datastore
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
from manager_rest.security import (SecuredResource,
                                   MissingPremiumFeatureResource)
from manager_rest.manager_exceptions import BadParametersError

from .. import rest_decorators, rest_utils
from ..responses_v3 import UserResponse

try:
    from cloudify_premium.multi_tenancy.secured_tenant_resource \
        import SecuredMultiTenancyResource
    _PREMIUM = True
except ImportError:
    SecuredMultiTenancyResource = MissingPremiumFeatureResource
    _PREMIUM = False


class User(SecuredResource):
    @authorize('user_get_self')
    @rest_decorators.marshal_with(UserResponse)
    def get(self):
        """
        Get details for the current user
        """
        return user_datastore.get_user(current_user.username)


class Users(SecuredMultiTenancyResource):
    @authorize('user_list')
    @rest_decorators.marshal_with(UserResponse)
    @rest_decorators.create_filters(models.User)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.User)
    @rest_decorators.search('username')
    def get(self, multi_tenancy, _include=None, filters=None, pagination=None,
            sort=None, search=None, **kwargs):
        """
        List users
        """
        return multi_tenancy.list_users(
            _include,
            filters,
            pagination,
            sort,
            search
        )

    @authorize('user_create')
    @rest_decorators.marshal_with(UserResponse)
    @rest_decorators.no_external_authenticator('create user')
    def put(self, multi_tenancy):
        """
        Create a user
        """
        request_dict = rest_utils.get_json_and_verify_params(
            {
                'username': {
                    'type': str,
                },
                'password': {
                    'type': str,
                },
                'role': {
                    'type': str,
                    'optional': True,
                },
                'created_at': {'type': str, 'optional': True},
                'last_login_at': {'type': str, 'optional': True},
                'first_login_at': {'type': str, 'optional': True},
            }
        )
        is_prehashed = rest_utils.verify_and_convert_bool(
            'is_prehashed', request_dict.pop('is_prehashed', False))

        timestamps = {}
        set_timestamp_checked = False
        for timestamp in 'created_at', 'first_login_at', 'last_login_at':
            if request_dict.get(timestamp):
                if not set_timestamp_checked:
                    check_user_action_allowed('set_timestamp', None, True)
                    set_timestamp_checked = True
                timestamps[timestamp] = rest_utils.parse_datetime_string(
                    request_dict.pop(timestamp))

        # The password shouldn't be validated here
        password = request_dict.pop('password')
        password = rest_utils.validate_and_decode_password(password)
        rest_utils.validate_inputs(request_dict)
        role = request_dict.get('role', constants.DEFAULT_SYSTEM_ROLE)
        rest_utils.verify_role(role, is_system_role=True)

        return multi_tenancy.create_user(
            request_dict['username'],
            password,
            role,
            is_prehashed=is_prehashed,
            created_at=timestamps.get('created_at'),
            first_login_at=timestamps.get('first_login_at'),
            last_login_at=timestamps.get('last_login_at'),
        )


class UsersIdPremium(SecuredMultiTenancyResource):
    @rest_decorators.marshal_with(UserResponse)
    def post(self, username, multi_tenancy):
        """
        Alter settings (e.g. password/role) for a certain user
        """
        request_dict = rest_utils.get_json_and_verify_params()
        password = request_dict.get('password')
        role_name = request_dict.get('role')
        show_getting_started = request_dict.get('show_getting_started')

        if password:
            if role_name:
                raise BadParametersError('Both `password` and `role` provided')
            if username != current_user.username:
                self.authorize_update()
            password = rest_utils.validate_and_decode_password(password)
            return multi_tenancy.set_user_password(username, password)

        self.authorize_update()
        if role_name:
            rest_utils.verify_role(role_name, is_system_role=True)
            return multi_tenancy.set_user_role(username, role_name)
        if show_getting_started is not None:
            show_getting_started = \
                rest_utils.verify_and_convert_bool('show_getting_started',
                                                   show_getting_started)
            return multi_tenancy.set_show_getting_started(
                username, show_getting_started)
        raise BadParametersError(
            'No valid user settings provided. Available settings: '
            'password, role, show_getting_started')

    @authorize('user_get')
    @rest_decorators.marshal_with(UserResponse)
    def get(self, username, multi_tenancy):
        """
        Get details for a single user
        """
        return multi_tenancy.get_user(username)

    @authorize('user_delete')
    def delete(self, username, multi_tenancy):
        """
        Delete a user
        """
        multi_tenancy.delete_user(username)
        return None, 204

    def authorize_update(self):
        # when running unittests, there is no authorization
        if config.instance.test_mode:
            return

        check_user_action_allowed('user_update')


class UsersIdCommunity(SecuredResource):
    @authorize('user_get')
    @rest_decorators.marshal_with(UserResponse)
    def get(self, username):
        """
        Get details for a single user
        """
        rest_utils.validate_inputs({'username': username})
        if username != current_user.username:
            raise BadParametersError('Cannot get details of a different user')
        return user_datastore.get_user(current_user.username)

    @rest_decorators.marshal_with(UserResponse)
    def post(self, username):
        """
        Change user's password or getting started flag
        """
        request_dict = rest_utils.get_json_and_verify_params()
        password = request_dict.get('password')
        show_getting_started = request_dict.get('show_getting_started')

        if username != current_user.username:
            raise BadParametersError('Cannot change settings for '
                                     'a different user')

        user = user_datastore.get_user(current_user.username)
        if password:
            new_password = rest_utils.validate_and_decode_password(password)
            user.password = hash_password(new_password)
            user_datastore.commit()
            return user
        if show_getting_started is not None:
            set_show_getting_started = \
                rest_utils.verify_and_convert_bool('show_getting_started',
                                                   show_getting_started)
            user.show_getting_started = set_show_getting_started
            user_datastore.commit()
            return user
        raise BadParametersError(
            'No valid user settings provided. Available settings: '
            'password, show_getting_started')


UsersId = UsersIdPremium if _PREMIUM else UsersIdCommunity


class UsersActive(SecuredMultiTenancyResource):
    @authorize('user_set_activated')
    @rest_decorators.marshal_with(UserResponse)
    def post(self, username, multi_tenancy):
        """
        Activate a user
        """
        request_dict = rest_utils.get_json_and_verify_params({'action'})
        if request_dict['action'] == 'activate':
            return multi_tenancy.activate_user(username)
        else:
            return multi_tenancy.deactivate_user(username)


class UsersUnlock(SecuredMultiTenancyResource):
    @authorize('user_unlock')
    @rest_decorators.marshal_with(UserResponse)
    def post(self, username, multi_tenancy):
        """
        Unlock user account
        """
        rest_utils.validate_inputs({'username': username})
        return multi_tenancy.unlock_user(username)

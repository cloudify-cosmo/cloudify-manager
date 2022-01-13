#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from flask import request
from flask_security import current_user

from cloudify._compat import text_type
from cloudify.models_states import VisibilityState
from cloudify.cryptography_utils import encrypt, decrypt

from ... import utils
from .. import rest_decorators, rest_utils
from ..responses_v3 import SecretsListResponse
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
from manager_rest.storage import models, get_storage_manager
from manager_rest.resource_manager import get_resource_manager
from manager_rest.manager_exceptions import (ConflictError,
                                             ForbiddenError,
                                             IllegalActionError)


class SecretsKey(SecuredResource):
    @authorize('secret_get')
    @rest_decorators.marshal_with(models.Secret)
    def get(self, key):
        """
        Get secret by key
        """
        rest_utils.validate_inputs({'key': key})
        secret = get_storage_manager().get(models.Secret, key)
        secret_dict = secret.to_dict()
        if secret_dict['is_hidden_value'] and not \
                rest_utils.is_hidden_value_permitted(secret):
            # Hide the value of the secret
            secret_dict['value'] = ''
        else:
            # Returns the decrypted value
            secret_dict['value'] = decrypt(secret.value)
        return secret_dict

    @authorize('secret_create')
    @rest_decorators.marshal_with(models.Secret)
    def put(self, key, **kwargs):
        """
        Create a new secret
        """
        request_dict = rest_utils.get_json_and_verify_params({
            'value': {
                'type': text_type,
            },
            'update_if_exists': {
                'optional': True,
            }
        })
        value = request_dict['value']
        update_if_exists = rest_utils.verify_and_convert_bool(
            'update_if_exists',
            request_dict.get('update_if_exists', False),
        )
        rest_utils.validate_inputs({'key': key})

        sm = get_storage_manager()
        timestamp = utils.get_formatted_timestamp()
        try:
            new_secret = models.Secret(
                id=key,
                value=value,
                created_at=timestamp,
                updated_at=timestamp,
            )
            return sm.put(new_secret)
        except ConflictError:
            secret = sm.get(models.Secret, key)
            if secret and update_if_exists:
                secret.value = value
                secret.updated_at = timestamp
                return sm.update(secret, validate_global=True)
            raise

    @authorize('secret_update')
    @rest_decorators.marshal_with(models.Secret)
    def patch(self, key):
        """
        Update an existing secret
        """
        rest_utils.validate_inputs({'key': key})
        if not request.json:
            raise IllegalActionError('Update a secret request must include at '
                                     'least one parameter to update')
        secret = get_storage_manager().get(models.Secret, key)
        self._validate_secret_modification_permitted(secret)
        self._update_is_hidden_value(secret)
        self._update_visibility(secret)
        self._update_value(secret)
        self._update_owner(secret)
        secret.updated_at = utils.get_formatted_timestamp()
        return get_storage_manager().update(secret, validate_global=True)

    @authorize('secret_delete')
    def delete(self, key):
        """
        Delete a secret
        """
        rest_utils.validate_inputs({'key': key})
        storage_manager = get_storage_manager()
        secret = storage_manager.get(models.Secret, key)
        self._validate_secret_modification_permitted(secret)
        storage_manager.delete(secret, validate_global=True)
        return None, 204

    def _validate_secret_modification_permitted(self, secret):
        if secret.is_hidden_value and \
                not rest_utils.is_hidden_value_permitted(secret):
            raise ForbiddenError(
                'User `{0}` is not permitted to modify the hidden value '
                'secret `{1}`'.format(current_user.username, secret.key)
            )

    def _update_is_hidden_value(self, secret):
        is_hidden_value = request.json.get('is_hidden_value')
        if is_hidden_value is None:
            return
        is_hidden_value = rest_utils.verify_and_convert_bool(
            'is_hidden_value',
            is_hidden_value
        )
        # Only the creator of the secret and the admins can change a secret
        # to be hidden value
        if not rest_utils.is_hidden_value_permitted(secret):
            raise ForbiddenError(
                'User `{0}` is not permitted to modify the secret `{1}` '
                'to be hidden value'.format(current_user.username, secret.key)
            )
        secret.is_hidden_value = is_hidden_value

    def _update_visibility(self, secret):
        visibility = rest_utils.get_visibility_parameter(
            optional=True,
            valid_values=VisibilityState.STATES,
        )
        if visibility:
            get_resource_manager().validate_visibility_value(
                models.Secret,
                secret,
                visibility
            )
            secret.visibility = visibility

    def _update_value(self, secret):
        request_dict = rest_utils.get_json_and_verify_params({
            'value': {'type': text_type, 'optional': True}
        })
        value = request_dict.get('value')
        if value:
            secret.value = encrypt(value)

    def _update_owner(self, secret):
        request_dict = rest_utils.get_json_and_verify_params({
            'creator': {'type': text_type, 'optional': True}
        })
        creator_username = request_dict.get('creator')
        if not creator_username:
            return
        check_user_action_allowed('set_owner', None, True)
        creator = rest_utils.valid_user(request_dict.get('creator'))
        if creator:
            secret.creator = creator


class Secrets(SecuredResource):
    @authorize('secret_list')
    @rest_decorators.marshal_with(SecretsListResponse)
    @rest_decorators.create_filters(models.Secret)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Secret)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            all_tenants=None, search=None, **kwargs):
        """
        List secrets
        """
        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        return get_storage_manager().list(
            models.Secret,
            include=_include,
            filters=filters,
            substr_filters=search,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants,
            get_all_results=get_all_results
        )

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

from ... import utils
from manager_rest import config
from .. import rest_decorators, rest_utils
from manager_rest import cryptography_utils
from ..responses_v3 import SecretsListResponse
from manager_rest.utils import is_administrator
from manager_rest.security import SecuredResource
from manager_rest.manager_exceptions import ConflictError
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.resource_manager import get_resource_manager


class SecretsKey(SecuredResource):
    @rest_decorators.exceptions_handled
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
                self._is_value_permitted(secret_dict['created_by']):
            # Hide the value of the secret
            secret_dict['value'] = ''
        else:
            # Returns the decrypted value
            encryption_key = config.instance.security_encryption_key
            secret_dict['value'] = cryptography_utils.decrypt(encryption_key,
                                                              secret.value)
        return secret_dict

    @rest_decorators.exceptions_handled
    @authorize('secret_create')
    @rest_decorators.marshal_with(models.Secret)
    def put(self, key, **kwargs):
        """
        Create a new secret
        """
        request_dict = rest_utils.get_json_and_verify_params({
            'value': {
                'type': unicode,
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
                get_resource_manager().validate_modification_permitted(secret)
                secret.value = value
                secret.updated_at = timestamp
                return sm.update(secret)
            raise

    @rest_decorators.exceptions_handled
    @authorize('secret_update')
    @rest_decorators.marshal_with(models.Secret)
    def patch(self, key):
        """
        Update an existing secret
        """
        request_dict = rest_utils.get_json_and_verify_params({'value'})
        rest_utils.validate_inputs({'key': key})

        secret = get_storage_manager().get(models.Secret, key)
        get_resource_manager().validate_modification_permitted(secret)
        secret.value = self._encrypt_secret_value(request_dict['value'])
        secret.updated_at = utils.get_formatted_timestamp()
        return get_storage_manager().update(secret)

    @rest_decorators.exceptions_handled
    @authorize('secret_delete')
    @rest_decorators.marshal_with(models.Secret)
    def delete(self, key):
        """
        Delete a secret
        """
        rest_utils.validate_inputs({'key': key})
        storage_manager = get_storage_manager()
        secret = storage_manager.get(models.Secret, key)
        get_resource_manager().validate_modification_permitted(secret)
        return storage_manager.delete(secret)

    def _encrypt_secret_value(self, value):
        encryption_key = config.instance.security_encryption_key
        return cryptography_utils.encrypt(encryption_key, value)

    def _is_value_permitted(self, creator):
        current_tenant = get_storage_manager().current_tenant
        current_username = current_user.username
        return is_administrator(current_tenant) or creator == current_username


class Secrets(SecuredResource):
    @rest_decorators.exceptions_handled
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

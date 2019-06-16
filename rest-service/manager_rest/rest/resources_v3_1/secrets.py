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

from cloudify.models_states import VisibilityState
from cloudify.cryptography_utils import (encrypt,
                                         decrypt,
                                         generate_key_using_password)
from manager_rest import manager_exceptions
from manager_rest.security import (SecuredResource, authorization)
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.resource_manager import (create_secret,
                                           add_to_dict_values,
                                           get_resource_manager)
from manager_rest.rest import (rest_decorators,
                               resources_v3,
                               rest_utils)


class SecretsSetGlobal(SecuredResource):

    @rest_decorators.exceptions_handled
    @authorize('resource_set_global')
    @rest_decorators.marshal_with(models.Secret)
    def patch(self, key):
        """
        Set the secret's visibility to global
        """
        return get_resource_manager().set_global_visibility(
            models.Secret,
            key,
            VisibilityState.GLOBAL
        )


class SecretsSetVisibility(SecuredResource):

    @rest_decorators.exceptions_handled
    @authorize('secret_update')
    @rest_decorators.marshal_with(models.Secret)
    def patch(self, key):
        """
        Set the secret's visibility
        """
        visibility = rest_utils.get_visibility_parameter()
        return get_resource_manager().set_visibility(models.Secret,
                                                     key,
                                                     visibility)


class SecretsKey(resources_v3.SecretsKey):
    @rest_decorators.exceptions_handled
    @authorize('secret_create')
    @rest_decorators.marshal_with(models.Secret)
    def put(self, key, **kwargs):
        """
        Create a new secret or update an existing secret if the flag
        update_if_exists is set to true
        """
        return create_secret(key=key)


class SecretsExport(SecuredResource):
    @rest_decorators.exceptions_handled
    @authorize('secret_create')
    @rest_decorators.create_filters(models.Secret)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, filters=None, all_tenants=None, search=None):
        passphrase = request.args.get('_passphrase')
        secrets = get_storage_manager().list(
            models.Secret,
            filters=filters,
            substr_filters=search,
            all_tenants=all_tenants,
            get_all_results=True
        )
        return self._create_export_response(secrets, passphrase)

    def _create_export_response(self, secrets, password):
        secrets_list = []
        for secret in secrets.items:
            if secret.is_hidden_value and not \
                    rest_utils.is_hidden_value_permitted(secret):
                continue
            new_secret = {'key': secret.key,
                          'value': decrypt(secret.value),
                          'visibility': secret.visibility,
                          'tenant_name': secret.tenant_name,
                          'is_hidden_value': secret.is_hidden_value,
                          'encrypted': False}
            secrets_list.append(new_secret)
        if password:
            self._encrypt_values(secrets_list, password)
        return secrets_list

    @staticmethod
    def _encrypt_values(secrets_list, password):
        key = generate_key_using_password(password)
        for secret in secrets_list:
            secret['value'] = encrypt(secret['value'], key)
            secret['encrypted'] = True


class SecretsImport(SecuredResource):
    @rest_decorators.exceptions_handled
    @authorize('secret_create')
    def post(self):
        response = {}
        colliding_secrets = {}
        overridden_secrets = {}
        request_dict = self._validate_import_secrets_params()
        secrets_list = request_dict.get('secrets_list')
        existing_tenants = [tenant.name for tenant in
                            get_storage_manager().list(models.Tenant)]
        tenant_map_dict = request_dict.get('tenant_map_dict')
        if tenant_map_dict:
            tenant_map_dict = self._validate_tenant_map(tenant_map_dict,
                                                        existing_tenants)
        passphrase = request_dict.get('passphrase')
        override_collisions = request_dict.get('override_collisions')
        formed_secrets_list, secrets_errors = self._format_secrets(
                                                    secrets_list,
                                                    tenant_map_dict,
                                                    passphrase,
                                                    existing_tenants,
                                                    override_collisions)
        for secret in formed_secrets_list:
            collision_state, tenant_name = create_secret(
                imported_secret=secret)
            if collision_state == 'overridden':
                add_to_dict_values(overridden_secrets, tenant_name,
                                   secret['key'])
            elif collision_state == 'collision':
                add_to_dict_values(colliding_secrets, tenant_name,
                                   secret['key'])
        response['overridden_secrets'] = overridden_secrets
        response['colliding_secrets'] = colliding_secrets
        response['secrets_errors'] = secrets_errors
        return response

    @staticmethod
    def _validate_import_secrets_params():
        request_dict = rest_utils.get_json_and_verify_params({
            'secrets_list': {'type': list, 'optional': False},
            'tenant_map_dict': {'type': dict, 'optional': True},
            'passphrase': {'type': unicode, 'optional': True},
            'override_collisions': {'type': bool, 'optional': False}
        })
        return request_dict

    @staticmethod
    def _format_secrets(secrets_list,
                        tenant_map_dict,
                        passphrase,
                        existing_tenants,
                        override_collisions):
        secrets_errors_dict = {}
        formed_secret_list = []
        key = generate_key_using_password(passphrase) if passphrase else None
        for i, secret in enumerate(secrets_list):
            secret['update_if_exists'] = override_collisions
            secret_errors = {}
            missing_attributes = SecretsImport.\
                _validate_secret_attr(secret, secret_errors)
            if missing_attributes:
                secret_errors['missing secret attributes'] = missing_attributes
            valid_encrypt, encrypted = SecretsImport._encrypted_attr(
                secret_errors, missing_attributes, secret)
            valid_value = True if 'value' not in secret_errors else False
            SecretsImport._encrypt_value(valid_value, valid_encrypt,
                                         encrypted, key, secret_errors, secret)
            SecretsImport._is_hidden_attr(secret_errors, missing_attributes,
                                          secret)
            SecretsImport._tenant_name_attr(secret_errors, missing_attributes,
                                            secret, tenant_map_dict,
                                            existing_tenants)
            SecretsImport._visibility_attr(secret_errors, missing_attributes,
                                           secret)
            if secret_errors:
                secrets_errors_dict[i] = secret_errors
            else:
                formed_secret_list.append(secret)

        return formed_secret_list, secrets_errors_dict

    @staticmethod
    def _validate_tenant_name(secret, tenant_map_dict, existing_tenants):
        tenant_name_exists = True
        tenant_name_authorized = True
        tenant_name = secret['tenant_name']
        if tenant_map_dict and (tenant_name in tenant_map_dict):
            tenant_name = tenant_map_dict[tenant_name]
        if tenant_name not in existing_tenants:
            tenant_name_exists = False
        if tenant_name_exists and not authorization.is_user_action_allowed(
                'secret_create', tenant_name):
            tenant_name_authorized = False

        return tenant_name_exists, tenant_name_authorized, tenant_name

    @staticmethod
    def _validate_bool_attr(secret, attr):
        valid = True
        try:
            attr = rest_utils.verify_and_convert_bool('', secret[attr])
        except manager_exceptions.BadParametersError:
            valid = False
        return valid, attr

    @staticmethod
    def _validate_tenant_map(tenant_map, existing_tenants_list):
        not_existing_tenants = []
        for origin_tenant, destination_tenant in tenant_map.iteritems():
            if destination_tenant not in existing_tenants_list:
                not_existing_tenants.append(destination_tenant)
            if origin_tenant == destination_tenant:
                del tenant_map[origin_tenant]
        not_exist_msg = '{0} tenants do not exist'.format(not_existing_tenants)
        if not_existing_tenants:
            raise manager_exceptions.BadParametersError(not_exist_msg)
        return tenant_map

    @staticmethod
    def _validate_secret_attr(secret, secret_errors):
        secret_attributes = ['key', 'value', 'is_hidden_value', 'tenant_name',
                             'visibility', 'encrypted']
        missing_attr = rest_utils.verify_dict_params(secret, secret_attributes)
        for attr in secret_attributes:
            if attr not in ['is_hidden_value', 'encrypted']:
                SecretsImport._attr_not_empty(secret_errors, missing_attr,
                                              secret, attr)
        return missing_attr

    @staticmethod
    def _encrypted_attr(secret_errors, missing_attributes, secret):
        valid_encrypt = False
        encrypted = False
        if 'encrypted' not in missing_attributes:
            valid_encrypt, encrypted = SecretsImport. \
                _validate_bool_attr(secret, 'encrypted')
            if not valid_encrypt:
                secret_errors['encrypted'] = 'Not boolean'
        return valid_encrypt, encrypted

    @staticmethod
    def _value_attr(secret_errors, missing_attributes, secret):
        return SecretsImport._attr_not_empty(secret_errors, missing_attributes,
                                             secret, 'value')

    @staticmethod
    def _attr_not_empty(secret_errors, missing_attributes, secret, attr):
        not_empty_attr = True
        if attr not in missing_attributes:
            if (not secret[attr]) or not secret[attr].strip():
                secret_errors[attr] = 'Empty'
                not_empty_attr = False
        return not_empty_attr

    @staticmethod
    def _encrypt_value(valid_value, valid_encrypt, encrypted, key,
                       secret_errors, secret):
        if valid_value and valid_encrypt:
            if encrypted and key:
                secret['value'] = decrypt(secret['value'], key)
            elif encrypted and not key:
                secret_errors['No passphrase'] = 'The secret is encrypted ' \
                                                 'but no passphrase was given'

    @staticmethod
    def _is_hidden_attr(secret_errors, missing_attributes, secret):
        if 'is_hidden_value' not in missing_attributes:
            valid_is_hidden_value, is_hidden_value = SecretsImport. \
                _validate_bool_attr(secret, 'is_hidden_value')
            if not valid_is_hidden_value:
                secret_errors['is_hidden_value'] = 'Not boolean'
            else:
                secret['is_hidden_value'] = is_hidden_value

    @staticmethod
    def _tenant_name_attr(secret_errors, missing_attributes, secret,
                          tenant_map_dict, existing_tenants):
        if 'tenant_name' not in missing_attributes and ('tenant_name'
                                                        not in secret_errors):
            tenant_name_exists, tenant_name_authorized, tenant_name = \
                SecretsImport._validate_tenant_name(secret,
                                                    tenant_map_dict,
                                                    existing_tenants)
            not_auth_msg = 'User `{0}` is not permitted to perform the' \
                           ' action secrets_create in the tenant: {1}'.\
                format(current_user.username, str(tenant_name))
            not_exist_msg = 'The tenant `{0}` was not found '.\
                format(str(tenant_name))
            if tenant_name_authorized and tenant_name_exists:
                secret['tenant_name'] = tenant_name
            elif not tenant_name_authorized:
                secret_errors['tenant_name'] = not_auth_msg
            elif not tenant_name_exists:
                secret_errors['tenant_name'] = not_exist_msg

    @staticmethod
    def _visibility_attr(secret_errors, missing_attributes, secret):
        if 'visibility' not in missing_attributes and ('visibility' not in
                                                       secret_errors):
            visibility = secret['visibility']
            if visibility not in ['private', 'tenant', 'global']:
                secret_errors['visibility'] = 'Not a valid visibility'

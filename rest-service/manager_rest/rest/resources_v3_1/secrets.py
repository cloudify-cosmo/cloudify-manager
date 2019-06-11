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
from enum import Enum

from cloudify.models_states import VisibilityState
from cloudify.cryptography_utils import (encrypt,
                                         decrypt,
                                         generate_key_using_password)
from manager_rest import utils, manager_exceptions
from manager_rest.security import (SecuredResource, authorization)
from manager_rest.manager_exceptions import ConflictError
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.resource_manager import get_resource_manager
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
        secret_params = self._get_secret_params(key)
        encrypted_value = encrypt(secret_params['value'])
        sm = get_storage_manager()
        timestamp = utils.get_formatted_timestamp()

        try:
            new_secret = models.Secret(
                id=key,
                value=encrypted_value,
                created_at=timestamp,
                updated_at=timestamp,
                visibility=secret_params['visibility'],
                is_hidden_value=secret_params['is_hidden_value']
            )
            return sm.put(new_secret)
        except ConflictError:
            secret = sm.get(models.Secret, key)
            if secret and secret_params['update_if_exists']:
                secret.value = encrypted_value
                secret.updated_at = timestamp
                return sm.update(secret, validate_global=True)
            raise

    def _get_secret_params(self, key):
        rest_utils.validate_inputs({'key': key})
        request_dict = rest_utils.get_json_and_verify_params({
            'value': {'type': unicode}
        })
        update_if_exists = rest_utils.verify_and_convert_bool(
            'update_if_exists',
            request_dict.get('update_if_exists', False),
        )
        is_hidden_value = rest_utils.verify_and_convert_bool(
            'is_hidden_value',
            request_dict.get('is_hidden_value', False),
        )
        visibility_param = rest_utils.get_visibility_parameter(
            optional=True,
            valid_values=VisibilityState.STATES,
        )
        visibility = get_resource_manager().get_resource_visibility(
            models.Secret,
            key,
            visibility_param
        )

        secret_params = {
            'value': request_dict['value'],
            'update_if_exists': update_if_exists,
            'visibility': visibility,
            'is_hidden_value': is_hidden_value
        }
        return secret_params


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
                          'encrypted': 'False'}
            secrets_list.append(new_secret)
        if password:
            self._encrypt_values(secrets_list, password)
        return secrets_list

    @staticmethod
    def _encrypt_values(secrets_list, password):
        key = generate_key_using_password(password)
        for secret in secrets_list:
            secret['value'] = encrypt(secret['value'], key)
            secret['encrypted'] = 'True'


class SecretsImport(SecuredResource):
    class SecretsCollision(Enum):
        create = 1
        override = 2
        collision = 3

    @rest_decorators.exceptions_handled
    @authorize('secret_create')
    def post(self):
        # import pydevd
        # pydevd.settrace('192.168.8.110', port=53100, stdoutToServer=True,
        #                 stderrToServer=True, suspend=True)

        response = {}
        colliding_secrets = []
        overridden_secrets = []
        request_dict = self._validate_import_secrets_params()
        secrets_list = request_dict.get('secrets_list')
        # self._validate_secrets_list(secrets_list)
        existing_tenants = [tenant.name for tenant in
                            get_storage_manager().list(models.Tenant)]
        tenant_map_dict = request_dict.get('tenant_map_dict')
        if tenant_map_dict:
            tenant_map_dict = self._validate_tenant_map(tenant_map_dict,
                                                        existing_tenants)

        passphrase = request_dict.get('passphrase')
        formed_secrets_list, secrets_errors = self._format_secrets(
                                                    secrets_list,
                                                    tenant_map_dict,
                                                    passphrase,
                                                    existing_tenants)
        override_collisions = request_dict.get('override_collisions')
        for secret in formed_secrets_list:
            collision_state = self._create_imported_secret(secret,
                                                           override_collisions)
            if collision_state == SecretsImport.SecretsCollision.override:
                overridden_secrets.append(secret['key'])
            elif collision_state == SecretsImport.SecretsCollision.collision:
                colliding_secrets.append(secret['key'])
        response['overridden_secrets'] = overridden_secrets
        response['colliding_secrets'] = colliding_secrets
        response['secrets_errors'] = secrets_errors
        return response

    @staticmethod
    def _validate_import_secrets_params():
        request_dict = rest_utils.get_json_and_verify_params({
            'secrets_list': {'type': list, 'optional': False},
            'tenant_map_dict': {'type': dict, 'optional': True},
            'passphrase': {'type': str, 'optional': True},
            'override_collisions': {'type': bool, 'optional': False}
        })
        return request_dict

    @staticmethod
    def _format_secrets(secrets_list,
                        tenant_map_dict,
                        passphrase,
                        existing_tenants):
        secrets_errors_dict = {}
        formed_secret_list = []
        key = generate_key_using_password(passphrase) if passphrase else None
        for i, secret in enumerate(secrets_list):
            secret_errors = {}

            missing_attributes = SecretsImport._validate_secret_attr(secret)
            if missing_attributes:
                secret_errors['missing secret attributes'] = missing_attributes

            valid_value = False
            valid_encrypt = False
            encrypted = False
            if 'encrypted' not in missing_attributes:
                valid_encrypt, encrypted = SecretsImport.\
                    _validate_bool_attr(secret, 'encrypted')
                if not valid_encrypt:
                    secret_errors['encrypted'] = 'Not boolean'
            if 'value' not in missing_attributes:
                valid_value = True if secret['value'].strip() else False
                if not valid_value:
                    secret_errors['value'] = 'Empty'
            if valid_value and valid_encrypt:
                if encrypted and key:
                    secret['value'] = decrypt(secret['value'], key)
                elif encrypted and not key:
                    secret_errors['No passphrase'] = 'The secret is ' \
                                                     'encrypted but no' \
                                                     ' passphrase was given'

            if 'is_hidden_value' not in missing_attributes:
                valid_is_hidden_value, _ = SecretsImport. \
                    _validate_bool_attr(secret, 'is_hidden_value')
                if not valid_is_hidden_value:
                    secret_errors['is_hidden_value'] = 'Not boolean'

            if 'tenant_name' not in missing_attributes:
                tenant_name_exists, tenant_name_authorized, tenant_name = \
                    SecretsImport._validate_tenant_name(secret,
                                                        tenant_map_dict,
                                                        existing_tenants)
                not_auth_msg = 'User `{0}` is not permitted to perform the' \
                               ' action secrets_create in the tenant: {1}'.\
                    format(current_user.username, str(tenant_name))
                not_exist_msg = 'The following tenant was not found: {0}'.\
                    format(str(tenant_name))
                if tenant_name_authorized and tenant_name_exists:
                    secret['tenant_name'] = tenant_name
                elif not tenant_name_authorized:
                    secret_errors['tenant_name'] = not_auth_msg
                elif not tenant_name_exists:
                    secret_errors['tenant_name'] = not_exist_msg

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
    def _validate_secret_attr(secret):
        secret_attributes = ['key', 'value', 'is_hidden_value', 'tenant_name',
                             'visibility', 'encrypted']
        missing_attr = rest_utils.verify_dict_params(secret, secret_attributes)
        return missing_attr

    @staticmethod
    def _create_imported_secret(secret, override_collisions):
        """
        :param secret: The secret to be created
        :param override_collisions: whether or not we should override existing
        secrets
        :return: The function will verify the user is allowed to create the
        secret in the specific tenant and returns the status of creation:
        create / collision / override
        """
        encrypted_value = encrypt(secret['value'])
        sm = get_storage_manager()
        timestamp = utils.get_formatted_timestamp()
        tenant_name = secret['tenant_name']
        secret_tenant = sm.get(models.Tenant,
                               tenant_name,
                               filters={'name': tenant_name})
        try:
            new_secret = models.Secret(
                id=secret['key'],
                value=encrypted_value,
                created_at=timestamp,
                updated_at=timestamp,
                visibility=secret['visibility'],
                is_hidden_value=secret['is_hidden_value'],
                tenant=secret_tenant
            )
            sm.put(new_secret)
            return SecretsImport.SecretsCollision.create
        except ConflictError:
            existing_secret = sm.get(models.Secret,
                                     secret['key'],
                                     filters={'id': secret['key'],
                                              'tenant_name': tenant_name},
                                     all_tenants=True)
            if existing_secret and override_collisions:
                existing_secret.value = encrypted_value
                existing_secret.updated_at = timestamp
                existing_secret.is_hidden_value = secret['is_hidden_value']
                existing_secret.visibility = secret['visibility']
                sm.update(existing_secret, validate_global=True)
                return SecretsImport.SecretsCollision.override
            else:
                return SecretsImport.SecretsCollision.collision

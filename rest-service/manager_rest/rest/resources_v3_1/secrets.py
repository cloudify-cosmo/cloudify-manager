from flask import request

from cloudify._compat import text_type
from cloudify.models_states import VisibilityState
from cloudify.cryptography_utils import (encrypt,
                                         decrypt,
                                         generate_key_using_password)

from manager_rest import manager_exceptions
from manager_rest.utils import current_tenant
from manager_rest.flask_utils import get_tenant_by_name
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
from manager_rest.storage import models, get_storage_manager
from manager_rest.resource_manager import (create_secret,
                                           update_secret,
                                           add_to_dict_values,
                                           get_resource_manager,
                                           update_imported_secret)
from manager_rest.security import SecuredResource
from manager_rest.rest import rest_decorators, resources_v3, rest_utils


class SecretsSetGlobal(SecuredResource):

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
    @authorize('secret_create')
    @rest_decorators.marshal_with(models.Secret)
    def put(self, key, **kwargs):
        """
        Create a new secret or update an existing secret if the flag
        update_if_exists is set to true
        """
        secret = self._get_secret_params(key)
        if not secret.get('value'):
            raise manager_exceptions.BadParametersError(
                'Cannot create a secret with empty value: {0}'.format(key)
            )
        try:
            return create_secret(key=key, secret=secret, tenant=current_tenant)
        except manager_exceptions.ConflictError:
            if secret['update_if_exists']:
                existing_secret = get_storage_manager().get(models.Secret, key)
                return update_secret(existing_secret, secret)
            raise

    @staticmethod
    def _get_secret_params(key):
        rest_utils.validate_inputs({'key': key})
        request_dict = rest_utils.get_json_and_verify_params({
            'value': {'type': text_type}
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
    @authorize('secret_export')
    @rest_decorators.create_filters(models.Secret)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, filters=None, all_tenants=None, search=None):
        passphrase = request.args.get('_passphrase')
        include_metadata = request.args.get('_include_metadata')
        secrets = get_storage_manager().list(
            models.Secret,
            filters=filters,
            substr_filters=search,
            all_tenants=all_tenants,
            get_all_results=True,
        )
        return self._create_export_response(secrets, passphrase,
                                            include_metadata)

    def _create_export_response(self, secrets, password, include_metadata):
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
            if include_metadata:
                new_secret['creator'] = secret.created_by
                new_secret['created_at'] = secret.created_at
                new_secret['updated_at'] = secret.updated_at
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
    @authorize('secret_import')
    def post(self):
        response = {}
        colliding_secrets = {}
        request_dict = self._validate_import_secrets_params()
        tenant_map = request_dict.get('tenant_map')
        passphrase = request_dict.get('passphrase')
        secrets_list = request_dict.get('secrets_list')
        override_collisions = request_dict.get('override_collisions')
        existing_tenants = [tenant.name for tenant in
                            get_storage_manager().list(models.Tenant)]
        self._validate_tenant_map(tenant_map, existing_tenants)
        secrets_errors = self._import_secrets(secrets_list, tenant_map,
                                              passphrase, existing_tenants,
                                              colliding_secrets,
                                              override_collisions)
        response['colliding_secrets'] = colliding_secrets
        response['secrets_errors'] = secrets_errors
        return response

    @staticmethod
    def _validate_import_secrets_params():
        request_dict = rest_utils.get_json_and_verify_params({
            'secrets_list': {'type': list, 'optional': False},
            'tenant_map': {'type': dict, 'optional': True},
            'passphrase': {'type': text_type, 'optional': True},
            'override_collisions': {'type': bool, 'optional': False}
        })
        return request_dict

    def _import_secrets(self, secrets_list, tenant_map, passphrase,
                        existing_tenants, colliding_secrets, override):
        all_secrets_errors = {}
        encryption_key = (generate_key_using_password(passphrase) if
                          passphrase else None)
        for i, secret in enumerate(secrets_list):
            secret_errors = {}
            missing_fields = []
            self._is_missing_field(secret, 'key', missing_fields)
            self._validate_is_hidden_field(secret, missing_fields,
                                           secret_errors)
            self._validate_visibility_field(secret, missing_fields,
                                            secret_errors)
            self._handle_secret_tenant(secret, tenant_map, existing_tenants,
                                       missing_fields, secret_errors)
            self._check_timestamp_and_owner(secret, secret_errors)
            self._handle_encryption(secret, encryption_key, missing_fields,
                                    secret_errors)
            if missing_fields:
                secret_errors['missing secret fields'] = missing_fields
            if secret_errors:
                all_secrets_errors[i] = secret_errors
            else:
                self._import_secret(secret, colliding_secrets, override)
        return all_secrets_errors

    def _check_timestamp_and_owner(self, secret, secret_errors):
        if 'created_at' in secret or 'updated_at' in secret:
            try:
                check_user_action_allowed('set_timestamp',
                                          secret['tenant_name'])
            except manager_exceptions.ForbiddenError as err:
                secret_errors['timestamp'] = str(err)
        if 'creator' in secret:
            try:
                check_user_action_allowed('set_owner',
                                          secret['tenant_name'])
            except manager_exceptions.ForbiddenError as err:
                secret_errors['creator'] = str(err)
            try:
                secret['creator'] = rest_utils.valid_user(
                    secret['creator'])
            except manager_exceptions.BadParametersError as err:
                secret_errors['creator_valid'] = str(err)

    def _validate_is_hidden_field(self, secret, missing_fields, secret_errors):
        if self._is_missing_field(secret, 'is_hidden_value', missing_fields):
            return
        is_hidden_value = self._validate_boolean(secret, 'is_hidden_value')
        if is_hidden_value is None:
            secret_errors['is_hidden_value'] = 'Not boolean'
        else:
            secret['is_hidden_value'] = is_hidden_value

    def _validate_visibility_field(self, secret, missing_fields,
                                   secret_errors):
        if self._is_missing_field(secret, 'visibility', missing_fields):
            return

        visibility = secret['visibility']
        if visibility not in VisibilityState.STATES:
            secret_errors['visibility'] = 'Not a valid visibility'
            return

        if visibility == VisibilityState.GLOBAL:
            try:
                get_resource_manager().validate_global_permitted(models.Secret,
                                                                 secret['key'],
                                                                 visibility)
            except (manager_exceptions.IllegalActionError,
                    manager_exceptions.ForbiddenError) as error:
                secret_errors['visibility'] = str(error)

    def _handle_secret_tenant(self, secret, tenant_map, existing_tenants,
                              missing_fields, secret_errors):
        if self._is_missing_field(secret, 'tenant_name', missing_fields):
            return
        tenant_name = secret['tenant_name']
        if tenant_map and tenant_name in tenant_map:
            secret['tenant_name'] = tenant_map[tenant_name]
        self._validate_tenant_action(secret['tenant_name'], existing_tenants,
                                     secret_errors)

    @staticmethod
    def _validate_tenant_action(tenant_name, existing_tenants, secret_errors):
        """
        Ensure the tenant exists and that the current user is authorized to
        perform the `secret_create` action
        """

        if tenant_name not in existing_tenants:
            secret_errors['tenant_name'] = 'The tenant `{0}` was not' \
                                           ' found'.format(str(tenant_name))
        else:
            try:
                check_user_action_allowed('secret_create', tenant_name)
            except manager_exceptions.ForbiddenError as err:
                secret_errors['tenant_name'] = str(err)

    def _handle_encryption(self, secret, encryption_key,
                           missing_fields, secret_errors):
        """
        Asserts 'encrypted' field is boolean, and decrypts the secrets' value
        when encrypted == True
        """
        invalid_value = self._is_missing_field(secret, 'value', missing_fields)
        if self._is_missing_field(secret, 'encrypted', missing_fields):
            return
        is_encrypted = self._validate_boolean(secret, 'encrypted')
        if is_encrypted is None:
            secret_errors['encrypted'] = 'Not boolean'
        elif is_encrypted and not invalid_value:
            self._decrypt_value(secret, encryption_key, secret_errors)

    @staticmethod
    def _decrypt_value(secret, encryption_key, secret_errors):
        if encryption_key:
            secret['value'] = decrypt(secret['value'], encryption_key)
        else:
            secret_errors['No passphrase'] = 'The secret is encrypted ' \
                                             'but no passphrase was given'

    def _import_secret(self, secret, colliding_secrets, override_collisions):
        try:
            tenant = get_tenant_by_name(secret['tenant_name'])
            create_secret(key=secret['key'], secret=secret, tenant=tenant,
                          created_at=secret.get('created_at'),
                          updated_at=secret.get('updated_at'),
                          creator=secret.get('creator'))
        except manager_exceptions.ConflictError:
            if override_collisions:
                existing_secret = self._get_secret_object(secret)
                update_imported_secret(existing_secret, secret)
            add_to_dict_values(colliding_secrets, secret['tenant_name'],
                               secret['key'])

    @staticmethod
    def _get_secret_object(secret):
        return models.Secret.query.filter_by(
            id=secret['key'],
            tenant_name=secret['tenant_name']).first()

    @staticmethod
    def _is_missing_field(secret, field, missing_fields):
        value = secret[field] if field in secret else None
        empty_string = isinstance(value, text_type) and not value.strip()
        if value is None or empty_string:
            missing_fields.append(field)
            return True
        return False

    @staticmethod
    def _validate_boolean(secret, field):
        try:
            field = rest_utils.verify_and_convert_bool('', secret[field])
        except manager_exceptions.BadParametersError:
            return None
        return field

    @staticmethod
    def _validate_tenant_map(tenant_map, existing_tenants):
        if not tenant_map:
            return
        destination_tenants = set(tenant_map.values())
        missing_tenants = destination_tenants.difference(existing_tenants)
        if missing_tenants:
            missing_tenants = [str(tenant) for tenant in missing_tenants]
            raise manager_exceptions.BadParametersError(
                'The following destination tenants do not exist on the '
                'Manager: {0}'.format(missing_tenants))

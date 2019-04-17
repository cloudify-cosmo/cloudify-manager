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

from cloudify.cryptography_utils import encrypt
from cloudify.models_states import VisibilityState

from manager_rest import utils
from manager_rest.security import SecuredResource
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

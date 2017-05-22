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

from manager_rest.security import SecuredResource
from manager_rest.utils import get_formatted_timestamp
from manager_rest.storage import models, get_storage_manager

from .. import rest_decorators, rest_utils
from ..responses_v3 import SecretsListResponse


class SecretsKey(SecuredResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Secret)
    def get(self, key):
        """
        Get secret by key
        """

        rest_utils.validate_inputs({'key': key})
        return get_storage_manager().get(models.Secret, key)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Secret)
    def put(self, key):
        """
        Create a new secret
        """

        key, value = self._validate_secret_inputs(key)

        return get_storage_manager().put(models.Secret(
            id=key,
            value=value,
            created_at=get_formatted_timestamp(),
            updated_at=get_formatted_timestamp()
        ))

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Secret)
    def patch(self, key):
        """
        Update an existing secret
        """

        key, value = self._validate_secret_inputs(key)
        secret = get_storage_manager().get(models.Secret, key)
        secret.value = value
        secret.updated_at = get_formatted_timestamp()
        return get_storage_manager().update(secret)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Secret)
    def delete(self, key):
        """
        Delete a secret
        """

        rest_utils.validate_inputs({'key': key})
        storage_manager = get_storage_manager()
        secret = storage_manager.get(models.Secret, key)
        return storage_manager.delete(secret)

    def _validate_secret_inputs(self, key):
        request_dict = rest_utils.get_json_and_verify_params({'value'})
        value = request_dict['value']
        rest_utils.validate_inputs({'key': key})
        return key, value


class Secrets(SecuredResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(SecretsListResponse)
    @rest_decorators.create_filters(models.Secret)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Secret)
    @rest_decorators.all_tenants
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            all_tenants=None, **kwargs):
        """
        List secrets
        """

        return get_storage_manager().list(
            models.Secret,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants
        )

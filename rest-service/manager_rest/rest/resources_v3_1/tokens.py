#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

from manager_rest.rest import responses
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.rest.rest_decorators import exceptions_handled, marshal_with


class UserTokens(SecuredResource):

    @exceptions_handled
    @marshal_with(responses.Tokens)
    @authorize('user_token')
    def get(self, user_id):
        """
        Get token by user id
        """
        sm = get_storage_manager()
        user = sm.get(models.User, user_id)
        token = user.get_auth_token()
        return dict(username=user.username,
                    value=token, role=user.role)

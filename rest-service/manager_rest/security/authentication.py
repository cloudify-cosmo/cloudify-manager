#########
# Copyright (c) 2013-2019 Cloudify Platform Ltd. All rights reserved
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

from flask_security import current_user
from manager_rest.manager_exceptions import UnauthorizedError, NoAuthProvided


def authenticate(request):
    """Require that a user is authenticated"""
    if not current_user.is_authenticated:
        raise NoAuthProvided()
    if current_user.is_locked or not current_user.active:
        raise UnauthorizedError(
            'Authentication failed for <User '
            f'username=`{current_user.username}`>. '
            'Wrong credentials or locked account')
    return current_user

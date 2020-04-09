########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import hashlib

from flask import g
from werkzeug.local import LocalProxy

from cloudify import constants
from manager_rest.storage import get_storage_manager, models


@LocalProxy
def current_execution():
    return getattr(g, 'current_execution', None)


def set_current_execution(execution):
    """
    Sets the current execution, lasts for the lifetime of the request.
    """
    g.current_execution = execution


def get_current_execution_by_token(execution_token):
    sm = get_storage_manager()
    hashed = hashlib.sha256(execution_token.encode('ascii')).hexdigest()
    token_filter = {models.Execution.token: hashed}
    executions = sm.full_access_list(models.Execution, filters=token_filter)
    if len(executions) != 1:  # Only one execution should match the token
        return None
    return executions[0]


def get_execution_token_from_request(request):
    return request.headers.get(constants.CLOUDIFY_EXECUTION_TOKEN_HEADER)

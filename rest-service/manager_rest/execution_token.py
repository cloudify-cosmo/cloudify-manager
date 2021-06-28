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
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from cloudify import constants
from manager_rest.storage import models, db


@LocalProxy
def current_execution():
    return getattr(g, 'current_execution', None)


def set_current_execution(execution):
    """Sets the current execution, lasts for the lifetime of the request."""
    g.current_execution = execution


def get_current_execution_by_token(execution_token):
    hashed = hashlib.sha256(execution_token.encode('ascii')).hexdigest()
    try:
        return (
            models.Execution.query
            .filter_by(token=hashed)
            # tenant and creator are going to be fetched soon, so join them
            .options(db.joinedload(models.Execution.tenant))
            .options(db.joinedload(models.Execution.creator))
            .one()  # Only one execution should match the token
        )
    except (MultipleResultsFound, NoResultFound):
        return None


def get_execution_token_from_request(request):
    return request.headers.get(constants.CLOUDIFY_EXECUTION_TOKEN_HEADER)

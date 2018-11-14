#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
#

from flask_restful_swagger import swagger
from sqlalchemy import (
    asc,
    bindparam,
    desc,
    func,
    literal_column,
    or_ as sql_or
)
from toolz import dicttoolz
from copy import deepcopy

from manager_rest import manager_exceptions, utils
from manager_rest.rest import rest_decorators
from manager_rest.rest.rest_utils import get_json_and_verify_params
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import db, get_storage_manager
from manager_rest.storage.models_states import VisibilityState
from manager_rest.rest.responses_v2 import ListResponse
from manager_rest.rest.responses_v3_1 import LogEvent
from manager_rest.storage.resource_models import (
    Blueprint,
    Deployment,
    Execution,
    Event,
    Log,
    Node,
    NodeInstance,
)


class Events(SecuredResource):

    """Events resource.

    Through the events endpoint a user can retrieve both events and logs as
    stored in the SQL database.

    """

    DEFAULT_SEARCH_SIZE = 10000

    type_map = {
        'cloudify_event': Event,
        'cloudify_log': Log
    }

    @swagger.operation(
        responseclass='List[Event]',
        nickname="list events",
        notes='Returns a list of events for optionally provided filters'
    )
    @rest_decorators.exceptions_handled
    @authorize('event_list')
    @rest_decorators.marshal_with(LogEvent)
    @rest_decorators.create_filters()
    @rest_decorators.paginate
    @rest_decorators.rangeable
    @rest_decorators.projection
    @rest_decorators.sortable()
    def get(self, _include=None, filters=None,
            pagination=None, sort=None, range_filters=None, **kwargs):
        """List events using a SQL backend.

        :returns: Events found in the SQL backend
        :rtype: dict(str)

        """

        size = pagination.get('size', self.DEFAULT_SEARCH_SIZE)
        offset = pagination.get('offset', 0)

        type_filter = filters.pop('type', ['cloudify_event'])
        items = []

        sm = get_storage_manager()
        for elem_type in type_filter:
            items.extend(sm.list(
                self.type_map[elem_type],
                include=_include,
                filters=filters,
                get_all_results=True
            ).items)

        total = len(items)

        items = sorted(items, key=lambda x: x.timestamp)
        items = items[offset:offset + size]

        metadata = {
            'pagination': {
                'size': size,
                'offset': offset,
                'total': total
            }
        }

        return ListResponse(items=items, metadata=metadata)

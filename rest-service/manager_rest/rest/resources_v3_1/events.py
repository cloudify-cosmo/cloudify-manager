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
from sqlalchemy import literal, null

from manager_rest.rest import rest_decorators
from manager_rest.security import SecuredResource
from manager_rest.storage import db, get_storage_manager
from manager_rest.security.authorization import authorize
from manager_rest.rest.responses_v2 import ListResponse
from manager_rest.rest.responses_v3_1 import LogEvent
from manager_rest.storage.resource_models import (
    Execution,
    Event,
    Log,
)


class Events(SecuredResource):

    """Events resource.

    Through the events endpoint a user can retrieve both events and logs as
    stored in the SQL database.

    """

    DEFAULT_SEARCH_SIZE = 10000

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
        self.sm = get_storage_manager()

        pagination.setdefault('size', self.DEFAULT_SEARCH_SIZE)
        pagination.setdefault('offset', 0)

        type_filter = filters.pop('type', ['cloudify_event'])

        # Only returning events
        if type_filter == ['cloudify_event']:
            return self.sm.list(Event, filters=filters, pagination=pagination)

        # Only returning logs
        if type_filter == ['cloudify_log']:
            return self.sm.list(Log, filters=filters, pagination=pagination)

        # Returning both events and logs
        execution = self._get_execution(filters)

        events_query = self._get_events_query(execution)
        logs_query = self._get_logs_query(execution)

        query = events_query.union_all(logs_query)

        query = self._sort_query(query, sort)

        results, metadata = self._execute_query(query, pagination)
        return ListResponse(items=results, metadata=metadata)

    @staticmethod
    def _get_events_query(execution):
        events_query_columns = [
            Event.timestamp.label('timestamp'),
            Event.reported_timestamp.label('reported_timestamp'),
            Event.message.label('message'),
            Event.message_code.label('message_code'),
            Event.operation.label('operation'),
            Event.node_id.label('node_instance_id'),
            Event.source_id.label('source_id'),
            Event.target_id.label('target_id'),
            Event.visibility.label('visibility'),

            null().label('level'),
            null().label('logger'),

            Event.event_type.label('event_type'),
            Event.error_causes.label('error_causes'),

            literal(execution.id).label('execution_id'),
            literal(execution.deployment_id).label('deployment_id'),
            literal(execution.workflow_id).label('workflow_id'),

            literal('cloudify_event').label('type'),
        ]

        events_query = db.session.query(*events_query_columns)
        if execution:
            events_query = events_query.filter(Event.execution == execution)

        return events_query

    @staticmethod
    def _get_logs_query(execution):
        logs_query_columns = [
            Log.timestamp.label('timestamp'),
            Log.reported_timestamp.label('reported_timestamp'),
            Log.message.label('message'),
            Log.message_code.label('message_code'),
            Log.operation.label('operation'),
            Log.node_id.label('node_instance_id'),
            Log.source_id.label('source_id'),
            Log.target_id.label('target_id'),
            Log.visibility.label('visibility'),

            Log.level.label('level'),
            Log.logger.label('logger'),

            null().label('event_type'),
            null().label('error_causes'),

            literal(execution.id).label('execution_id'),
            literal(execution.deployment_id).label('deployment_id'),
            literal(execution.workflow_id).label('workflow_id'),

            literal('cloudify_log').label('type'),
        ]

        logs_query = db.session.query(*logs_query_columns)
        if execution:
            logs_query = logs_query.filter(Log.execution == execution)

        return logs_query

    def _get_execution(self, filters):
        execution = None
        execution_id = filters.get('execution_id')

        if execution_id:
            execution = self.sm.get(Execution, execution_id)

        return execution

    def _sort_query(self, query, sort):
        if sort:
            query = self.sm._sort_query(query, None, sort)
        else:
            query = query.order_by('reported_timestamp')
        return query

    def _execute_query(self, query, pagination):
        results, total, size, offset = self.sm._paginate(query,
                                                         pagination,
                                                         get_all_results=True)
        metadata = {
            'pagination': {
                'size': size,
                'offset': offset,
                'total': total
            }
        }
        return results, metadata

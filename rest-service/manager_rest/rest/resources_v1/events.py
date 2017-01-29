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

from datetime import datetime

from flask_restful_swagger import swagger
from sqlalchemy import (
    asc,
    bindparam,
    desc,
    func,
    literal_column,
)
from toolz import dicttoolz

from manager_rest import manager_exceptions
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    insecure_rest_method,
)
from manager_rest.rest.rest_utils import get_json_and_verify_params
from manager_rest.security import SecuredResource
from manager_rest.storage.models_base import db
from manager_rest.storage.resource_models import (
    Deployment,
    Execution,
    Event,
    Log,
)


class Events(SecuredResource):

    """Events resource.

    Throgh the events endpoint a user can retrieve both events and logs as
    stored in the SQL database.

    """

    DEFAULT_SEARCH_SIZE = 10000

    @staticmethod
    def _build_select_query(filters, pagination, sort):
        """Build query used to list events for a given execution.

        :param filters:
            Filter selection. It's used to decide if events:
                {'type': ['cloudify_event']}
            or both events and logs should be returned:
                {'type': ['cloudify_event', 'cloudify_log']}
        :type filters: dict(str, str)
        :param pagination:
            Parameters used to limit results returned in a single query.
            Expected values `size` and `offset` are mapped into SQL as `LIMIT`
            and `OFFSET`.
        :type pagination: dict(str, int)
        :param sort:
            Result sorting order. The only allowed and expected value is to
            sort by timestamp in ascending order:
                {'timestamp': 'asc'}
        :type sort: dict(str, str)
        :returns:
            A SQL query that returns the events found that match the conditions
            passed as arguments.
        :rtype: :class:`sqlalchemy.sql.elements.TextClause`

        """
        if not isinstance(filters, dict) or 'type' not in filters:
            raise manager_exceptions.BadParametersError(
                'Filter by type is expected')

        if 'cloudify_event' not in filters['type']:
            raise manager_exceptions.BadParametersError(
                'At least `type=cloudify_event` filter is expected')

        query = (
            db.session.query(
                Event.timestamp.label('timestamp'),
                Deployment.id.label('deployment_id'),
                Event.message,
                Event.message_code,
                Event.event_type,
                Event.operation,
                Event.node_id,
                literal_column('NULL').label('logger'),
                literal_column('NULL').label('level'),
                literal_column("'cloudify_event'").label('type'),
            )
            .filter(
                Event._execution_fk == Execution._storage_id,
                Execution._deployment_fk == Deployment._storage_id,
            )
        )

        if 'deployment_id' in filters:
            query = query.filter(Deployment.id.in_(filters['deployment_id']))

        if 'cloudify_log' in filters['type']:
            logs_query = (
                db.session.query(
                    Log.timestamp.label('timestamp'),
                    Deployment.id.label('deployment_id'),
                    Log.message,
                    literal_column('NULL').label('message_code'),
                    literal_column('NULL').label('event_type'),
                    Log.operation,
                    Log.node_id,
                    Log.logger,
                    Log.level,
                    literal_column("'cloudify_log'").label('type'),
                )
                .filter(
                    Log._execution_fk == Execution._storage_id,
                    Execution._deployment_fk == Deployment._storage_id,
                )
            )
            if 'deployment_id' in filters:
                logs_query = logs_query.filter(
                    Deployment.id.in_(filters['deployment_id']))
            query = query.union(logs_query)

        if 'execution_id' in filters:
            query = query.filter(Execution.id == bindparam('execution_id'))

        if '@timestamp' in sort:
            order_func = asc if sort['@timestamp'] == 'asc' else desc
            query = query.order_by(order_func('timestamp'))

        query = (
            query
            .limit(bindparam('limit'))
            .offset(bindparam('offset'))
        )

        return query

    @staticmethod
    def _build_count_query(filters):
        """Build query used to count events for a given execution.

        :param filters:
            Filter selection. It's used to decide if events:
                {'type': ['cloudify_event']}
            or both events and logs should be returned:
                {'type': ['cloudify_event', 'cloudify_log']}
        :type filters: dict(str, str)
        :returns:
            A SQL query that returns the number of events found that match the
            conditions passed as arguments.
        :rtype: :class:`sqlalchemy.sql.elements.TextClause`

        """
        if not isinstance(filters, dict) or 'type' not in filters:
            raise manager_exceptions.BadParametersError(
                'Filter by type is expected')

        if 'cloudify_event' not in filters['type']:
            raise manager_exceptions.BadParametersError(
                'At least `type=cloudify_event` filter is expected')

        events_query = (
            db.session.query(func.count('*').label('count'))
            .filter(
                Event._execution_fk == Execution._storage_id,
                Execution._deployment_fk == Deployment._storage_id,
            )
        )

        if 'execution_id' in filters:
            events_query.filter(Execution.id == bindparam('execution_id'))

        if 'cloudify_log' in filters['type']:
            logs_query = (
                db.session.query(func.count('*').label('count'))
                .filter(
                    Log._execution_fk == Execution._storage_id,
                    Execution._deployment_fk == Deployment._storage_id,
                )
            )
            if 'execution_id' in filters:
                logs_query = logs_query.filter(
                    Execution.id == bindparam('execution_id'))

            query = db.session.query(
                events_query.subquery().c.count +
                logs_query.subquery().c.count
            )
        else:
            query = db.session.query(events_query.subquery().c.count)

        return query

    @staticmethod
    def _map_event_to_es(_include, sql_event):
        """Restructure event data as if it was returned by elasticsearch.

        This restructuration is needed because the API in the past used
        elasticsearch as the backend and the client implementation still
        expects data that has the same shape as elasticsearch would return.

        :param _include:
            Projection used to get records from database (not currently used)
        :type _include: list(str)
        :param sql_event: Event data returned when SQL query was executed
        :type sql_event: :class:`sqlalchemy.util._collections.result`
        :returns: Event as would have returned by elasticsearch
        :rtype: dict(str)

        """
        event = {
            attr: getattr(sql_event, attr)
            for attr in sql_event.keys()
        }
        event['@timestamp'] = event['timestamp']

        event['message'] = {
            'text': event['message']
        }

        context_fields = [
            'deployment_id',
            'operation',
            'node_id',
        ]
        event['context'] = {
            field: event[field]
            for field in context_fields
        }
        for field in context_fields:
            del event[field]

        if event['type'] == 'cloudify_event':
            event['message']['arguments'] = None
            del event['logger']
            del event['level']
        elif event['type'] == 'cloudify_log':
            del event['event_type']

        for key, value in event.items():
            if isinstance(value, datetime):
                event[key] = '{}Z'.format(value.isoformat()[:-3])

        # Keep only keys passed in the _include request argument
        if _include is not None:
            event = dicttoolz.keyfilter(lambda key: key in _include, event)

        return event

    def _query_events(self):
        """Query events using a SQL backend.

        :returns:
            Results using a format that resembles the one used by elasticsearch
            (more information about the format in :meth:`.._map_event_to_es`)
        :rtype: dict(str)

        """
        request_dict = get_json_and_verify_params()

        es_query = request_dict['query']['bool']

        _include = None
        # This is a trick based on the elasticsearch query pattern
        # - when only a filter is used it's in a 'must' section
        # - when multiple filters are used they're in a 'should' section
        if 'should' in es_query:
            filters = {'type': ['cloudify_event', 'cloudify_log']}
        else:
            filters = {'type': ['cloudify_event']}
        pagination = {
            'size': request_dict.get('size', self.DEFAULT_SEARCH_SIZE),
            'offset': request_dict['from'],
        }
        sort = {
            field: value['order']
            for es_sort in request_dict['sort']
            for field, value in es_sort.items()
        }

        params = {
            'execution_id': (
                es_query['must'][0]['match']['context.execution_id']),
            'limit': pagination['size'],
            'offset': pagination['offset'],
        }

        count_query = self._build_count_query(filters)
        total = count_query.params(**params).scalar()

        select_query = self._build_select_query(filters, pagination, sort)

        events = [
            self._map_event_to_es(_include, event)
            for event in select_query.params(**params).all()
        ]

        results = {
            'hits': {
                'hits': [
                    {'_source': event}
                    for event in events
                ],
                'total': total,
            },
        }

        return results

    @swagger.operation(
        nickname='events',
        notes='Returns a list of events for the provided ElasticSearch query. '
              'The response format is as ElasticSearch response format.',
        parameters=[{'name': 'body',
                     'description': 'ElasticSearch query.',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'}],
        consumes=['application/json']
    )
    @exceptions_handled
    @insecure_rest_method
    def get(self, **kwargs):
        """List events using a SQL backend.

        :returns: Events found in the SQL backend
        :rtype: dict(str)

        """
        return self._query_events()

    @swagger.operation(
        nickname='events',
        notes='Returns a list of events for the provided ElasticSearch query. '
              'The response format is as ElasticSearch response format.',
        parameters=[{'name': 'body',
                     'description': 'ElasticSearch query.',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'}],
        consumes=['application/json']
    )
    @exceptions_handled
    @insecure_rest_method
    def post(self, **kwargs):
        """
        List events for the provided Elasticsearch query
        """
        return self._query_events()

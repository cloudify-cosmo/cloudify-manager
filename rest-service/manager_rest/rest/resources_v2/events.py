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
from sqlalchemy import bindparam

from manager_rest import manager_exceptions
from manager_rest.rest import (
    resources_v1,
    rest_decorators,
)
from manager_rest.storage.models_base import db
from manager_rest.storage.resource_models import (
    Deployment,
    Execution,
    Event,
    Log,
)
from manager_rest.storage import ListResult


class Events(resources_v1.Events):

    """Events resource.

    Through the events endpoint a user can retrieve both events and logs as
    stored in the SQL database.

    """

    @swagger.operation(
        responseclass='List[Event]',
        nickname="list events",
        notes='Returns a list of events for optionally provided filters'
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_events
    @rest_decorators.create_filters()
    @rest_decorators.paginate
    @rest_decorators.rangeable
    @rest_decorators.projection
    @rest_decorators.sortable()
    def get(self, _include=None, filters=None,
            pagination=None, sort=None, range_filters=None, **kwargs):
        """List events using a SQL backend.

        :param _include:
            Projection used to get records from database (not currently used)
        :type _include: list(str)
        :param filters:
            Filter selection.

            It's used to decide if events:
                {'type': ['cloudify_event']}
            or both events and logs should be returned:
                {'type': ['cloudify_event', 'cloudify_log']}

            Also it's used to get only events for a particular execution:
                {'execution_id': '<some uuid>'}
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
        :returns: Events that match the conditions passed as arguments
        :rtype: :class:`manager_rest.storage.storage_manager.ListResult`
        :param range_filters:
            Apparently was used to select a timestamp interval. It's not
            currently used.
        :type range_filters: dict(str)
        :returns: Events found in the SQL backend
        :rtype: :class:`manager_rest.storage.storage_manager.ListResult`

        """
        size = pagination.get('size', self.DEFAULT_SEARCH_SIZE)
        offset = pagination.get('offset', 0)
        params = {
            'limit': size,
            'offset': offset,
        }

        count_query = self._build_count_query(filters, range_filters,
                                              self.current_tenant.id)
        total = count_query.params(**params).scalar()

        select_query = self._build_select_query(filters, sort, range_filters,
                                                self.current_tenant.id)

        results = [
            self._map_event_to_dict(_include, event)
            for event in select_query.params(**params).all()
        ]

        metadata = {
            'pagination': {
                'size': size,
                'offset': offset,
                'total': total,
            }
        }
        return ListResult(results, metadata)

    @rest_decorators.exceptions_handled
    def post(self):
        raise manager_exceptions.MethodNotAllowedError()

    @swagger.operation(
        responseclass='List[Event]',
        nickname="delete events",
        notes='Deletes events according to a passed Deployment ID'
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_events
    @rest_decorators.create_filters()
    @rest_decorators.paginate
    @rest_decorators.rangeable
    @rest_decorators.projection
    @rest_decorators.sortable()
    def delete(self, filters=None, pagination=None, sort=None,
               range_filters=None, **kwargs):
        """Delete events/logs connected to a certain Deployment ID."""
        if not isinstance(filters, dict) or 'type' not in filters:
            raise manager_exceptions.BadParametersError(
                'Filter by type is expected')

        if 'cloudify_event' not in filters['type']:
            raise manager_exceptions.BadParametersError(
                'At least `type=cloudify_event` filter is expected')

        executions_query = (
            db.session.query(Execution._storage_id)
            .filter(
                Execution._deployment_fk == Deployment._storage_id,
                Deployment.id == bindparam('deployment_id'),
                Execution._tenant_id == bindparam('tenant_id')
            )
        )
        params = {
            'deployment_id': filters['deployment_id'][0],
            'tenant_id': self.current_tenant.id
        }

        delete_event_query = (
            db.session.query(Event)
            .filter(
                Event._execution_fk.in_(executions_query),
                Event._tenant_id == bindparam('tenant_id')
            )
            .params(**params)
        )
        total = delete_event_query.delete(synchronize_session=False)

        if 'cloudify_log' in filters['type']:
            delete_log_query = (
                db.session.query(Log)
                .filter(
                    Log._execution_fk.in_(executions_query),
                    Log._tenant_id == bindparam('tenant_id')
                )
                .params(**params)
            )
            total += delete_log_query.delete('fetch')

        metadata = {
            'pagination': dict(pagination, total=total)
        }

        # Commit bulk row deletions to database
        db.session.commit()

        # We don't really want to return all of the deleted events,
        # so it's a bit of a hack to return the deleted element count.
        return ListResult([total], metadata)

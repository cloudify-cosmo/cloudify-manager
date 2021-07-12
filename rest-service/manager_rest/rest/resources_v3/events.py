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

from datetime import datetime
import json

from ..resources_v2 import Events as v2_Events

from manager_rest import manager_exceptions
from manager_rest.storage import get_storage_manager, models, db
from manager_rest.security.authorization import authorize
from manager_rest.rest import rest_utils
from manager_rest.rest.rest_decorators import detach_globals
from manager_rest.execution_token import current_execution


def _strip_nul(text):
    """Remove NUL values from the text, so that it can be treated as text

    There should likely be no NUL values in human-readable logs anyway.
    """
    return text.replace('\x00', '<NUL>')


class Events(v2_Events):
    """Events resource.

    Through the events endpoint a user can retrieve both events and logs as
    stored in the SQL database.
    """

    UNUSED_FIELDS = ['id', 'node_id', 'message_code']

    @authorize('event_create', allow_if_execution=True)
    @detach_globals
    def post(self):
        request_dict = rest_utils.get_json_and_verify_params({
            'events': {'optional': True},
            'logs': {'optional': True},
            'execution_id': {'optional': True},
        })
        sm = get_storage_manager()
        exc = current_execution._get_current_object()
        if exc is None:
            exc_id = request_dict.get('execution_id')
            if exc_id is None:
                raise manager_exceptions.ConflictError(
                    'No execution passed, and not authenticated by '
                    'an execution token')
            exc = sm.get(models.Execution, request_dict.get('execution_id'))
        exc_params = {
            '_execution_fk': exc._storage_id,
            '_tenant_id': exc._tenant_id,
            '_creator_id': exc._creator_id,
            'visibility': exc.visibility,
        }
        raw_events = request_dict.get('events') or []
        raw_logs = request_dict.get('logs') or []
        if not raw_events and not raw_logs:
            return None, 204

        with sm.transaction():
            for ev in raw_events:
                db.session.execute(
                    self._event_from_raw_event(sm, ev, exc_params))
            for log in raw_logs:
                db.session.execute(
                    self._log_from_raw_log(sm, log, exc_params))
        return None, 201

    def _event_from_raw_event(self, sm, raw_event, exc_params):
        task_error_causes = raw_event['context'].get('task_error_causes')
        if task_error_causes is not None:
            task_error_causes = json.dumps(task_error_causes)
        return models.Event.__table__.insert().values(
            timestamp=datetime.utcnow(),
            reported_timestamp=datetime.utcnow(),
            event_type=raw_event['event_type'],
            message=_strip_nul(raw_event['message']['text']),
            message_code=raw_event.get('message_code'),
            operation=raw_event.get('operation'),
            node_id=raw_event['context'].get('node_id'),
            source_id=raw_event['context'].get('source_id'),
            target_id=raw_event['context'].get('target_id'),
            error_causes=task_error_causes,
            **exc_params,
        )

    def _log_from_raw_log(self, sm, raw_log, exc_params):
        return models.Log.__table__.insert().values(
            timestamp=datetime.utcnow(),
            reported_timestamp=datetime.utcnow(),
            logger=raw_log['logger'],
            level=raw_log['level'],
            message=_strip_nul(raw_log['message']['text']),
            message_code=raw_log.get('message_code'),
            operation=raw_log.get('operation'),
            node_id=raw_log['context'].get('node_id'),
            source_id=raw_log['context'].get('source_id'),
            target_id=raw_log['context'].get('target_id'),
            **exc_params,
        )

    @staticmethod
    def _map_event_to_dict(_include, sql_event):
        """Map event to a dictionary to be sent as an API response.

        In this implementation, the goal is to return a flat structure as
        opposed to the nested one that was returned by Elasticsearch in the
        past (see v1 implementation for more information).

        :param _include:
            Projection used to get records from database
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

        for unused_field in Events.UNUSED_FIELDS:
            if unused_field in event:
                del event[unused_field]

        if event['type'] == 'cloudify_event':
            del event['logger']
            del event['level']
        elif event['type'] == 'cloudify_log':
            del event['event_type']

        # Keep only keys passed in the _include request argument
        # TBD: Do the projection at the database level
        if _include is not None:
            event = {k: v for k, v in event.items() if k in _include}

        return event

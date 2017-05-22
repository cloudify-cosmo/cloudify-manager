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
#

from toolz import dicttoolz

from ..resources_v2 import Events as v2_Events


class Events(v2_Events):
    """Events resource.

    Through the events endpoint a user can retrieve both events and logs as
    stored in the SQL database.

    """

    UNUSED_FIELDS = ['id', 'node_id', 'message_code']

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
        event['reported_timestamp'] = event['timestamp']

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
            event = dicttoolz.keyfilter(lambda key: key in _include, event)

        return event

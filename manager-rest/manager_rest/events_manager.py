#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'idanmo'


import os
import config
import json
from os import path
from responses import DeploymentEvents


class EventsManager(object):

    def __init__(self, events_file_extension='.log'):
        self._events_file_extension = events_file_extension

    def get_deployment_events(self, deployment_id, first_event=0,
                              events_count=500, only_bytes=False):
        if only_bytes:
            deployment_events_bytes = self.get_deployment_events_bytes(
                deployment_id)
            return DeploymentEvents(
                id=deployment_id,
                first_event=-1,
                last_event=-1,
                events=[],
                deployment_total_events=-1,
                deployment_events_bytes=deployment_events_bytes)
        else:
            (events, deployment_events_bytes) = \
                self._read_deployment_events_from_file(deployment_id)
            deployment_total_events = len(events)
            if first_event < len(events) and events_count > 0:
                last_event = min(len(events), first_event + events_count)-1
                events = events[first_event:last_event+1]
            else:
                first_event = -1
                last_event = -1
                events = []
            events = map(lambda x: json.loads(x), events)
            return DeploymentEvents(
                id=deployment_id,
                first_event=first_event,
                last_event=last_event,
                events=events,
                deployment_total_events=deployment_total_events,
                deployment_events_bytes=deployment_events_bytes)

    def get_deployment_events_bytes(self, deployment_id):
        events_file = self._get_deployment_events_file_name(deployment_id)
        try:
            return path.getsize(events_file)
        except OSError:
            pass
        return 0

    def _read_deployment_events_from_file(self, deployment_id):
        events_file = self._get_deployment_events_file_name(deployment_id)
        try:
            with open(events_file, 'r') as f:
                raw_events = f.read()
                events = filter(lambda x: len(x) > 0,
                                raw_events.split(os.linesep))
                return events, len(raw_events)
        except IOError:
            return [], 0

    def _get_deployment_events_file_name(self, deployment_id):
        return path.join(config.instance().events_files_path,
                         "{0}{1}".format(deployment_id,
                                         self._events_file_extension))


_instance = EventsManager()


def reset():
    global _instance
    _instance = EventsManager()


def instance():
    return _instance

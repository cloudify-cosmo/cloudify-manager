#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

import bernhard
import os
import json


def send_event(node_id, host, service, type, value):
    event = {
        'host': host,
        'service': service,
        type: value,
        'tags': ['name={0}'.format(node_id)]
    }
    _send_event(event)


def send_log_event(log_record):
    host = _get_cosmo_properties()['ip']
    description = {
        'log_record': log_record
    }
    event = {
        'host': host,
        'service': 'celery-task-log',
        'state': '',
        'tags': ['cosmo-log'],
        'description': json.dumps(description)
    }
    try:
        _send_event(event)
    except:
        pass


def _send_event(event):
    client = _get_riemann_client()
    try:
        client.send(event)
    finally:
        client.disconnect()


def _get_riemann_client():
    host = _get_cosmo_properties()['management_ip']
    return bernhard.Client(host=host)


def _get_cosmo_properties():
    file_path = os.path.join(os.path.dirname(__file__), 'cosmo.txt')
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.loads(f.read())
    # when on management machine, cosmo.txt does not exist so management_ip and ip are
    # pointing to the management machine which is localhost.
    return {
        'management_ip': 'localhost',
        'ip': 'management'
    }


def test():
    send_event('vagrant_host', '10.0.0.5', 'vagrant machine status', 'state', 'running')


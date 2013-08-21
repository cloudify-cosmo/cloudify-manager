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
from cosmo.celery import get_management_ip


def send_event(node_id, host, service, type, value):
    client = bernhard.Client(host=get_management_ip())
    event = {
        'host': host,
        'service': service,
        type: value,
        'tags': ['name={0}'.format(node_id)]
    }
    try:
        client.send(event)
    finally:
        client.disconnect()


def test():
    send_event('vagrant_host', '10.0.0.5', 'vagrant machine status', 'running')

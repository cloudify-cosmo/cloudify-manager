########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

from cosmo.celery import celery
from cosmo.events import set_reachable as reachable
from cosmo.events import set_unreachable as unreachable
from time import time
from cosmo.runtime import inject_node_state

state = []
touched_time = None
unreachable_call_order = []


@celery.task
def make_reachable(__cloudify_id, **kwargs):
    reachable(__cloudify_id)
    global state
    state.append({
        'id': __cloudify_id,
        'time': time(),
        'relationships': kwargs['cloudify_runtime']
    })

@celery.task
def make_unreachable(__cloudify_id, **kwargs):
    unreachable(__cloudify_id)
    global unreachable_call_order
    unreachable_call_order.append({
        'id': __cloudify_id,
        'time': time()
    })


@celery.task
@inject_node_state
def set_property(__cloudify_id, property_name, value, node_state=None,  **kwargs):
    node_state.put(property_name, value)


@celery.task
def touch(**kwargs):
    global touched_time
    touched_time = time()


@celery.task
def get_state():
    return state

@celery.task
def get_touched_time():
    return touched_time

@celery.task
def is_unreachable_called(__cloudify__id, **kwargs):
    return next((x for x in unreachable_call_order if x['id'] == __cloudify__id), None)

@celery.task
def get_unreachable_call_order():
    return unreachable_call_order
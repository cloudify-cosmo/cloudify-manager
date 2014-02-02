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


from cloudify.decorators import operation
from time import time

state = []


@operation
def configure_connection(**kwargs):
    append_to_state(**kwargs)


@operation
def unconfigure_connection(**kwargs):
    append_to_state(**kwargs)


def append_to_state(__source_cloudify_id,
                    __target_cloudify_id,
                    __run_on_node_cloudify_id,
                    __source_properties,
                    __target_properties,
                    **kwargs):
    global state
    state.append({
        'source_id': __source_cloudify_id,
        'target_id': __target_cloudify_id,
        'time': time(),
        'source_properties': __source_properties,
        'target_properties': __target_properties,
        'run_on_node_id': __run_on_node_cloudify_id
    })


@operation
def get_state(**kwargs):
    return state

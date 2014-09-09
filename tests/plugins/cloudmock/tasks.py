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


import os
import json

from cloudify import ctx
from cloudify.decorators import operation

DATA_FILE_PATH = '/tmp/cloudmock-data.json'

RUNNING = "running"
NOT_RUNNING = "not_running"

DEFAULT_VM_IP = '10.0.0.1'

mem_data = {
    'machines': {},
    'raise_exception_on_start': False,
    'raise_exception_on_stop': False
}


@operation
def provision(**kwargs):
    data = _get_data()
    machines = data['machines']
    ctx.logger.info("cloudmock provision: [node_id=%s, machines=%s]",
                    ctx.node_id, machines)
    if ctx.node_id in machines:
        raise RuntimeError("machine with id [{0}] already exists"
                           .format(ctx.node_id))
    if ctx.properties.get('test_ip'):
        ctx.runtime_properties['ip'] = ctx.properties['test_ip']
    else:
        ctx.runtime_properties['ip'] = DEFAULT_VM_IP
    machines[ctx.node_id] = NOT_RUNNING
    _store_data(data)


@operation
def start(**kwargs):
    data = _get_data()
    machines = data['machines']
    ctx.send_event('starting machine event')
    ctx.logger.info("cloudmock start: [node_id={0}, machines={1}]".format(
        ctx.node_id, machines))
    if ctx.node_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist"
                           .format(ctx.node_id))
    machines[ctx.node_id] = RUNNING
    ctx.runtime_properties['id'] = ctx.node_id
    if data['raise_exception_on_start']:
        raise RuntimeError('Exception raised from CloudMock.start()!')
    _store_data(data)


@operation
def get_state(**kwargs):
    data = _get_data()
    return data['machines'][ctx.node_id] == RUNNING


@operation
def stop(**kwargs):
    data = _get_data()
    ctx.logger.info("stopping machine: " + ctx.node_id)
    if ctx.node_id not in data['machines']:
        raise RuntimeError("machine with id [{0}] does not exist"
                           .format(ctx.node_id))
    if data['raise_exception_on_stop']:
        raise RuntimeError('Exception raised from CloudMock.stop()!')
    data['machines'][ctx.node_id] = NOT_RUNNING
    _store_data(data)


@operation
def terminate(**kwargs):
    data = _get_data()
    ctx.logger.info("terminating machine: " + ctx.node_id)
    if ctx.node_id not in data['machines']:
        raise RuntimeError("machine with id [{0}] does not exist"
                           .format(ctx.node_id))
    del data['machines'][ctx.node_id]
    _store_data(data)


@operation
def get_machines(**kwargs):
    data = _get_data()
    return data['machines']


@operation
def set_raise_exception_on_start(**kwargs):
    data = _get_data()
    data['raise_exception_on_start'] = True
    _store_data(data)


@operation
def set_raise_exception_on_stop(**kwargs):
    data = _get_data()
    data['raise_exception_on_stop'] = True
    _store_data(data)


def _get_data():
    if os.path.exists(DATA_FILE_PATH):
        with open(DATA_FILE_PATH, 'r') as f:
            data = json.load(f)
            return data
    return mem_data


def _store_data(data):
    if os.path.exists(DATA_FILE_PATH):
        with open(DATA_FILE_PATH, 'w') as f:
            json.dump(data, f)
    else:
        global mem_data
        mem_data = data


def setup_plugin_file_based_mode():
    open(DATA_FILE_PATH, 'w').close()  # creating the file
    global mem_data
    _store_data(mem_data)


def teardown_plugin_file_based_mode():
    os.remove(DATA_FILE_PATH)

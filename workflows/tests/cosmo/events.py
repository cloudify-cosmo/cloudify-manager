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

from __future__ import absolute_import
from celery.utils.log import get_task_logger
import bernhard
import json

__author__ = 'idanmo'

logger = get_task_logger(__name__)


def get_cosmo_properties():
    """
    Mock.
    """
    return dict()


def set_reachable(node_id):
    """
    Sends a riemann event which causes the state cache to set the node's reachable state
    to true.
    """
    set_node_reachable_state(node_id, True)


def set_unreachable(node_id):
    """
    Sends a riemann event which causes the state cache to set the node's reachable state
    to true.
    """
    set_node_reachable_state(node_id, False)


def set_node_reachable_state(node_id, reachable):
    """
    Sends a riemann event which causes the state cache to set the node's property value
    """
    logger.info("Setting node '{0}' reachable state to '{1}'".format(node_id, reachable))
    riemann_client = bernhard.Client(host="localhost")
    state = 'reachable' if reachable else 'unreachable'
    event = {
        "host": node_id,
        "service": "node reachable state",
        "state": state,
        "tags": ["cosmo", "name={0}".format(node_id), state],
        "ttl": 9999,
        "description": json.dumps({
            "node_id": node_id,
            "policy": "",
            "message": ""
        })
    }
    riemann_client.send(event)


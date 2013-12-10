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
    set_property(node_id, 'reachable', 'true')


def set_unreachable(node_id):
    """
    Sends a riemann event which causes the state cache to set the node's reachable state
    to true.
    """
    set_property(node_id, 'reachable', 'false')


def set_property(node_id, property_name, value):
    """
    Sends a riemann event which causes the state cache to set the node's property value
    """
    logger.info("Setting {0} {1} property to '{2}'".format(node_id, property_name, value))
    riemann_client = bernhard.Client(host="localhost")
    event = {
        "host": node_id,
        "service": property_name,
        "state": value,
        "tags": ["cosmo"],
        "description": json.dumps({
            "node_id": node_id,
            "policy": "",
            "message": ""
        })
    }
    riemann_client.send(event)
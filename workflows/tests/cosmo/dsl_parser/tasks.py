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

import logging
from celery.utils.log import get_task_logger

__author__ = 'idanmo'

import json

NODES = "nodes"
NODES_EXTRA = "nodes_extra"

logger = get_task_logger(__name__)
logger.level = logging.DEBUG


def prepare_multi_instance_plan(nodes_plan_json):

    """
    JSON should include "nodes" and "nodes_extra".
    """
    plan = json.loads(nodes_plan_json)

    nodes = plan[NODES]
    nodes_extra = plan[NODES_EXTRA]

    nodes = create_multi_instance_nodes(nodes, nodes_extra)

    plan[NODES] = nodes

    return plan


def create_multi_instance_nodes(nodes, nodes_extra):
    pass


def create_node_instances(node, number_of_instances):

    instances = []

    for i in range(number_of_instances):

        # clone the original node
        node_copy = node.copy()

        # and change its id
        new_id = "{0}_{1}".format(node['id'], i + 1)
        node_copy['id'] = new_id

        # and change the host_id
        node_copy['host_id'] = "{0}_{1}".format(node_copy['host_id'], i + 1)

        logger.debug("generated new node instance {0}".format(node_copy))

        instances.append(node_copy)

    return instances











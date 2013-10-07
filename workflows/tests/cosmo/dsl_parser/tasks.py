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


def create_node_expansion_map(nodes, nodes_extra):

    """
    This method insepcts the current nodes and create an expansion map.
    That is, for every node, it should determine how many instances are needed in the final plan.
    """
    return {

    }


def create_multi_instance_nodes(nodes, nodes_extra):

    new_nodes = []

    nodes_expansion = create_node_expansion_map(nodes, nodes_extra)

    for node_id, number_of_instances in nodes_expansion.iteritems():
        node = get_node(node_id, nodes)
        instances = create_node_instances(node, number_of_instances)
        new_nodes.extend(instances)

    return new_nodes


def get_node(node_id, nodes):
    for node in nodes:
        if node_id == node['id']:
            return node
    raise RuntimeError("Could not find a node with id {0} in nodes".format(node_id))


def create_node_instances(node, number_of_instances):

    if number_of_instances == 1:

        # no need to duplicate. just return the original node
        return node

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
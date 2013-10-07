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


def get_node(tier_inner_node_name, application_name, nodes):

    expected_node_id = "{0}.{1}".format(application_name, tier_inner_node_name)

    for node in nodes:
        if expected_node_id == node['id']:
            return node
    raise RuntimeError("Could not find a node with id {0} in nodes".format(expected_node_id))


def create_multi_instance_nodes(nodes, nodes_extra):

    new_nodes = []
    inner_tier_node_ids = []

    # add inner tier nodes instances
    for node in nodes:

        if 'cloudify.tosca.types.tier' in nodes_extra[node['id']]['super_types']:

            # this is tier node. lets get all its inner nodes.
            tier_inner_nodes_names = node['properties']['nodes']

            # lets get how many instances
            tier_number_of_instances = node['properties']['number_of_instances']

            # lets get the tier id
            tier_id = node['id']

            # lets get the application name
            application_name = tier_id.split('.')[0]

            for tier_inner_node_name in tier_inner_nodes_names:

                # get the node dict object from all nodes by its name
                inner_node = get_node(tier_inner_node_name, application_name, nodes)

                # now lets create multiple instance for each tier node
                node_instances = create_node_instances(inner_node, tier_number_of_instances, tier_id)

                # add all these instances to the new nodes plan
                new_nodes.extend(node_instances)

                # save all inner tier node ids
                inner_tier_node_ids.append(inner_node['id'])

    # we need to leave all other nodes intact
    for node in nodes:

        # check if this is an inner tier node. if so, it was already handled
        if not node['id'] in inner_tier_node_ids:
            new_nodes.append(node)

    return new_nodes


def create_node_instances(node, tier_number_of_instances, tier_name):

    tier_simple_name = get_tier_simple_name(tier_name)

    instances = []

    for i in range(tier_number_of_instances):

        # clone the original node
        node_copy = node.copy()

        # and change its id
        application_name = node['id'].split('.')[0]
        node_simple_name = node['id'].split('.')[1]
        new_id = "{0}.{1}.{2}_{3}".format(application_name, tier_simple_name, node_simple_name, i + 1)
        node_copy['id'] = new_id

        logger.debug("generated new node instance {0}".format(node_copy))

        instances.append(node_copy)

    return instances


def get_tier_simple_name(tier_full_name):

    """
    Returns the simple name of the tier as defined in the YAML file.
    """

    return tier_full_name.split('.')[1]











#########
# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from flask import request

from manager_rest.security.authorization import authorize
from manager_rest.dsl_functions import (
    evaluate_node,
    evaluate_node_instance
)

from .. import rest_decorators
from ..resources_v1.nodes import NodeInstancesId as v1_NodeInstancesId
from ..resources_v2 import Nodes as v2_Nodes


class Nodes(v2_Nodes):
    @authorize('node_list')
    @rest_decorators.evaluate_functions
    def get(self, evaluate_functions=False, *args, **kwargs):
        # We don't skip marshalling, because we want an already marshalled
        # object, to avoid setting evaluated secrets in the node's properties
        nodes = super(Nodes, self).get(*args, **kwargs)
        if evaluate_functions:
            context = request.args.get('_instance_context')
            for node in nodes['items']:
                evaluate_node(node, instance_context=context)
        return nodes


class NodeInstancesId(v1_NodeInstancesId):
    @authorize('node_instance_get')
    @rest_decorators.evaluate_functions
    def get(self, evaluate_functions=False, *args, **kwargs):
        # We don't skip marshalling, because we want an already marshalled
        # object, to avoid setting evaluated secrets in the node instances's
        # runtime properties
        node_instance = super(NodeInstancesId, self).get(*args, **kwargs)
        if evaluate_functions:
            evaluate_node_instance(node_instance)
        return node_instance

#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

from dsl_parser import functions
from dsl_parser import exceptions as parser_exceptions

from manager_rest.storage import get_storage_manager
from manager_rest.storage import get_node as get_storage_node
from manager_rest.storage.models import NodeInstance, Deployment, Secret
from manager_rest.manager_exceptions import (
    FunctionsEvaluationError,
    DeploymentOutputsEvaluationError
)


def evaluate_intrinsic_functions(payload, deployment_id, context=None):
    context = context or {}
    sm = get_storage_manager()
    sm.get(Deployment, deployment_id, include=['id'])
    methods = _get_methods(deployment_id, sm)

    try:
        return functions.evaluate_functions(
            payload=payload,
            context=context,
            **methods)
    except parser_exceptions.FunctionEvaluationError, e:
        raise FunctionsEvaluationError(str(e))


def evaluate_deployment_outputs(deployment_id):
    sm = get_storage_manager()
    deployment = sm.get(Deployment, deployment_id, include=['outputs'])
    methods = _get_methods(deployment_id, sm)

    try:
        return functions.evaluate_outputs(
            outputs_def=deployment.outputs,
            **methods
            )
    except parser_exceptions.FunctionEvaluationError, e:
        raise DeploymentOutputsEvaluationError(str(e))


def _get_methods(deployment_id, storage_manager):
    """Retrieve a dict of all the callbacks necessary for function evaluation
    """
    def get_node_instances(node_id=None):
        filters = dict(deployment_id=deployment_id)
        if node_id:
            filters['node_id'] = node_id
        return storage_manager.list(NodeInstance, filters=filters).items

    def get_node_instance(node_instance_id):
        return storage_manager.get(NodeInstance, node_instance_id)

    def get_node(node_id):
        return get_storage_node(deployment_id, node_id)

    def get_secret(secret_key):
        return storage_manager.get(Secret, secret_key)

    return dict(
        get_node_instances_method=get_node_instances,
        get_node_instance_method=get_node_instance,
        get_node_method=get_node,
        get_secret_method=get_secret
    )

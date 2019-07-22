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

from collections import namedtuple

from dsl_parser import functions
from dsl_parser import exceptions as parser_exceptions

from cloudify import cryptography_utils

from manager_rest.storage import get_storage_manager
from manager_rest.storage import get_node as get_storage_node
from manager_rest.storage.models import NodeInstance, Deployment, Secret
from manager_rest.manager_exceptions import (
    FunctionsEvaluationError,
    DeploymentOutputsEvaluationError,
    DeploymentCapabilitiesEvaluationError
)

SecretType = namedtuple('Secret', 'key value')


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

    if not deployment.outputs:
        return {}

    try:
        return functions.evaluate_outputs(
            outputs_def=deployment.outputs,
            **methods
            )
    except parser_exceptions.FunctionEvaluationError, e:
        raise DeploymentOutputsEvaluationError(str(e))


def evaluate_deployment_capabilities(deployment_id):
    sm = get_storage_manager()
    deployment = sm.get(Deployment, deployment_id, include=['capabilities'])
    methods = _get_methods(deployment_id, sm)

    if not deployment.capabilities:
        return {}

    try:
        return functions.evaluate_capabilities(
            capabilities=deployment.capabilities,
            **methods
            )
    except parser_exceptions.FunctionEvaluationError, e:
        raise DeploymentCapabilitiesEvaluationError(str(e))


def get_secret_method():
    sm = get_storage_manager()
    methods = _get_methods(None, sm)
    return methods['get_secret_method']


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
        secret = storage_manager.get(Secret, secret_key)
        decrypted_value = cryptography_utils.decrypt(secret.value)
        return SecretType(secret_key, decrypted_value)

    def get_capability(capability_path):
        shared_dep_id, element_id = capability_path[0], capability_path[1]

        deployment = storage_manager.get(Deployment, shared_dep_id)
        capability = deployment.capabilities.get(element_id)

        if not capability:
            raise FunctionsEvaluationError(
                'Requested capability `{0}` is not declared '
                'in deployment `{1}`'.format(
                    element_id, shared_dep_id
                )
            )

        # We need to evaluate any potential intrinsic functions in the
        # capability's value in the context of the *shared* deployment,
        # instead of the current deployment, so we manually call the function
        capability = evaluate_intrinsic_functions(
            payload=capability,
            deployment_id=shared_dep_id
        )

        # If it's a nested property of the capability
        if len(capability_path) > 2:
            try:
                capability = \
                    functions.get_nested_attribute_value_of_capability(
                        capability['value'],
                        capability_path)
            except parser_exceptions.FunctionEvaluationError as e:
                raise FunctionsEvaluationError(str(e))

        return capability['value']

    return dict(
        get_node_instances_method=get_node_instances,
        get_node_instance_method=get_node_instance,
        get_node_method=get_node,
        get_secret_method=get_secret,
        get_capability_method=get_capability
    )

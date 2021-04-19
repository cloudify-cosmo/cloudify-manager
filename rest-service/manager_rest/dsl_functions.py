# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import namedtuple

from dsl_parser import functions
from dsl_parser import exceptions as parser_exceptions
from dsl_parser.constants import CAPABILITIES, EVAL_FUNCS_PATH_PREFIX_KEY

from cloudify import cryptography_utils

from manager_rest.storage import (get_storage_manager,
                                  get_node as get_storage_node)
from manager_rest.storage.models import (NodeInstance,
                                         Deployment,
                                         Secret,
                                         DeploymentLabel,)
from manager_rest.manager_exceptions import (
    FunctionsEvaluationError,
    DeploymentOutputsEvaluationError,
    DeploymentCapabilitiesEvaluationError,
)

SecretType = namedtuple('Secret', 'key value')


def evaluate_node(node):
    # dsl-parser uses name in plans, while the db storage uses id :(
    node['name'] = node['id']
    deployment_id = node['deployment_id']
    sm = get_storage_manager()
    sm.get(Deployment, deployment_id, include=['id'])
    storage = FunctionEvaluationStorage(deployment_id, sm)
    try:
        return functions.evaluate_node_functions(node, storage)
    except parser_exceptions.FunctionEvaluationError as e:
        raise FunctionsEvaluationError(str(e))


def evaluate_node_instance(instance):
    deployment_id = instance['deployment_id']
    sm = get_storage_manager()
    sm.get(Deployment, deployment_id, include=['id'])
    storage = FunctionEvaluationStorage(deployment_id, sm)

    try:
        return functions.evaluate_node_instance_functions(instance, storage)
    except parser_exceptions.FunctionEvaluationError as e:
        raise FunctionsEvaluationError(str(e))


def evaluate_intrinsic_functions(payload, deployment_id, context=None):
    context = context or {}
    sm = get_storage_manager()
    sm.get(Deployment, deployment_id, include=['id'])
    storage = FunctionEvaluationStorage(deployment_id, sm)

    try:
        return functions.evaluate_functions(payload, context, storage)
    except parser_exceptions.FunctionEvaluationError as e:
        raise FunctionsEvaluationError(str(e))


def evaluate_deployment_outputs(deployment_id):
    sm = get_storage_manager()
    deployment = sm.get(Deployment, deployment_id, include=['outputs'])
    storage = FunctionEvaluationStorage(deployment_id, sm)
    if not deployment.outputs:
        return {}

    try:
        return functions.evaluate_outputs(deployment.outputs, storage)
    except parser_exceptions.FunctionEvaluationError as e:
        raise DeploymentOutputsEvaluationError(str(e))


def evaluate_deployment_capabilities(deployment_id):
    sm = get_storage_manager()
    deployment = sm.get(Deployment, deployment_id, include=['capabilities'])
    storage = FunctionEvaluationStorage(deployment_id, sm)

    if not deployment.capabilities:
        return {}

    try:
        return functions.evaluate_capabilities(
            deployment.capabilities, storage)
    except parser_exceptions.FunctionEvaluationError as e:
        raise DeploymentCapabilitiesEvaluationError(str(e))


def get_secret_method(secret_key):
    sm = get_storage_manager()
    secret = sm.get(Secret, secret_key)
    decrypted_value = cryptography_utils.decrypt(secret.value)
    return SecretType(secret_key, decrypted_value)


class FunctionEvaluationStorage(object):
    """DB-backed storage for use when evaluating intrinsic functions.

    This has to be passed to dsl-parser's functions that evaluate intrinsic
    functions.
    """
    def __init__(self, deployment_id, storage_manager):
        self.sm = storage_manager
        self._deployment_id = deployment_id
        self.secret_method = get_secret_method

    def get_node_instances(self, node_id=None):
        filters = dict(deployment_id=self._deployment_id)
        if node_id:
            filters['node_id'] = node_id
        instances = self.sm.list(NodeInstance, filters=filters).items
        return [ni.to_dict() for ni in instances]

    def get_node_instance(self, node_instance_id):
        return self.sm.get(NodeInstance, node_instance_id).to_dict()

    def get_input(self, input_name):
        deployment = self.sm.get(Deployment, self._deployment_id)
        return deployment.inputs[input_name]

    def get_node(self, node_id):
        node = get_storage_node(self._deployment_id, node_id)
        return node.to_dict()

    def get_secret(self, secret_key):
        secret = self.sm.get(Secret, secret_key)
        decrypted_value = cryptography_utils.decrypt(secret.value)
        return SecretType(secret_key, decrypted_value)

    def get_capability(self, capability_path):
        shared_dep_id, element_id = capability_path[0], capability_path[1]

        deployment = self.sm.get(Deployment, shared_dep_id)
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
            deployment_id=shared_dep_id,
            context={EVAL_FUNCS_PATH_PREFIX_KEY: CAPABILITIES}
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

    def get_label(self, label_key, values_list_index):
        deployment = self.sm.get(Deployment, self._deployment_id)
        results = self.sm.list(
            DeploymentLabel,
            include=['value'],
            distinct=['value'],
            filters={'key': label_key,
                     '_labeled_model_fk': deployment._storage_id},
            get_all_results=True,
            sort={'created_at': 'asc', 'value': 'asc'}
        )
        label_values = [label.value for label in results]
        if not label_values:
            raise FunctionsEvaluationError(
                f'The deployment `{self._deployment_id}` does not have a '
                f'label with the key `{label_key}` assigned to it'
            )
        if values_list_index is not None:
            if values_list_index > (len(label_values) - 1):
                raise FunctionsEvaluationError(
                    f'The provided label-values list index is out of range. '
                    f'The key `{label_key}` has {len(label_values)} values'
                )
            return label_values[values_list_index]

        return label_values

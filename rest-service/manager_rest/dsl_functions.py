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
import json
import requests

from collections import namedtuple

from dsl_parser import functions
from dsl_parser import exceptions as parser_exceptions
from dsl_parser.constants import CAPABILITIES, EVAL_FUNCS_PATH_PREFIX_KEY

from cloudify import cryptography_utils

from cloudify.cryptography_utils import (
    decrypt,
)

from manager_rest.storage import (get_storage_manager,
                                  get_node as get_storage_node)
from manager_rest.storage.models import (NodeInstance,
                                         Deployment,
                                         Secret,
                                         DeploymentLabel,
                                         DeploymentGroup)
from manager_rest.manager_exceptions import (
    FunctionsEvaluationError,
    DeploymentOutputsEvaluationError,
    DeploymentCapabilitiesEvaluationError,
)

SecretType = namedtuple('SecretType', 'key value')

SECRETS_PROVIDER_SCHEMA = {
    'vault': {
        'connection_parameters': [
            'url',
            'token',
            'path',
        ],
    },
    'local': {
        'connection_parameters': [],
    },
}


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


def evaluate_intrinsic_functions(
    payload,
    deployment_id,
    context=None,
    sm=None,
):
    context = context or {}
    if sm is None:
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


def get_secret_method(secret_key, sm=None):
    if sm is None:
        sm = get_storage_manager()

    secret = sm.get(Secret, secret_key)

    if secret.provider:
        decrypted_value = get_secret_from_provider(secret)
    else:
        decrypted_value = cryptography_utils.decrypt(secret.value)

    return SecretType(secret_key, decrypted_value)


def get_secret_from_provider(secret):
    provider = secret.provider

    if provider.type == 'local':
        encrypted_value = secret.value
        decrypted_value = cryptography_utils.decrypt(encrypted_value)

        return decrypted_value
    elif provider.type == 'vault':
        connection_parameters = json.loads(
            decrypt(
                provider.connection_parameters,
            ),
        )
        decrypted_value = _get_secret_from_vault(
            connection_parameters['url'],
            connection_parameters['token'],
            connection_parameters['path'],
            secret.key,
        )

        return decrypted_value
    else:
        raise ValueError(
            f'Secrets Provider is not supported: {provider.type}',
        )


def _get_secret_from_vault(url, token, path, key):
    path_details = _get_vault_path_details(
        url,
        token,
        path,
    )

    if key not in path_details['data']['data']:
        raise ValueError(
            f'Secret {key} does not exist in Vault provider',
        )

    secret_value = path_details['data']['data'][key]

    return secret_value


def _get_vault_response(url, token, path):
    response = requests.get(
        f'{url}/v1/secret/data/{path}',
        headers={
            "X-Vault-Token": token,
        }
    )

    return response


def _get_vault_path_details(url, token, path):
    response = _get_vault_response(url, token, path)

    return response.json()


def check_vault_connection(url, token, path):
    vault_status = {
        'status': True,
        'message': '',
    }

    try:
        response = _get_vault_response(url, token, path)
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        vault_status['status'] = False
        vault_status['message'] = error

    return vault_status


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
        instances = self.sm.list(NodeInstance, filters=filters,
                                 get_all_results=True).items
        return [ni.to_dict() for ni in instances]

    def get_node_instance(self, node_instance_id):
        return self.sm.get(NodeInstance, node_instance_id).to_dict()

    def get_input(self, input_name):
        deployment = self.sm.get(Deployment, self._deployment_id)
        if not deployment.inputs:
            raise FunctionsEvaluationError(
                'Inputs are not yet evaluated for deployment '
                '`{}`'.format(self._deployment_id))
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
            context={EVAL_FUNCS_PATH_PREFIX_KEY: CAPABILITIES},
            sm=self.sm,
        )['value']
        return self._get_capability_by_path(capability, capability_path)

    def _get_capability_by_path(self, value, path):
        if len(path) <= 2:
            return value
        try:
            return functions.get_nested_attribute_value_of_capability(
                value, path)['value']
        except parser_exceptions.FunctionEvaluationError as e:
            raise FunctionsEvaluationError(str(e))

    def get_group_capability(self, capability_path):
        """Backend for the get_group_capability function.

        Supports several modes:
            - {get_group_cap: [gr_id, cap1]} -> just a list of cap1 from
              each deployment in the group
            - {get_group_cap: [gr_id, [cap1, cap2]]} -> a list of pairs,
              ie. a [value1, value2] 2-list for each deployment in the group
            - {get_group_cap: [gr_id, deployment_id:cap1]} -> instead of
              returning a list, returns a dict keyed by the deployment id
            - {get_group_cap: [gr_id, cap1, key, index]} -> also traverse
              each capability value, like c[key][index]. All deployments who
              have that capability at all, must have it in the correct format
              for this traversal.

        Deployments who don't have any of the requested capabilities are
        skipped in the output.
        """
        dep_group_id, element_ids = capability_path[0], capability_path[1]
        get_with_ids, element_ids = self._normalize_group_cap_element_id(
            element_ids)

        capabilities = {}
        for dep in self.sm.get(DeploymentGroup, dep_group_id).deployments:
            try:
                capabilities[dep.id] = self._get_deployment_group_caps(
                    dep, element_ids, capability_path)
            except ValueError:
                continue

        if get_with_ids:
            return capabilities
        else:
            return [caps for dep_id, caps in
                    sorted(capabilities.items(), key=lambda item: item[0])]

    def get_sys(self, entity, prop):
        deployment = self.sm.get(Deployment, self._deployment_id)
        if (entity, prop) == ('tenant', 'name'):
            return deployment.tenant.name
        elif (entity, prop) == ('deployment', 'blueprint'):
            return deployment.blueprint.id
        elif (entity, prop) == ('deployment', 'id'):
            return self._deployment_id
        elif (entity, prop) == ('deployment', 'name'):
            return deployment.display_name
        elif (entity, prop) == ('deployment', 'owner'):
            return deployment.creator.username
        raise FunctionsEvaluationError('Cannot retrieve this entity-property '
                                       f'pair: {entity}-{prop}')

    def get_consumers(self, prop):
        deployment = self.sm.get(Deployment, self._deployment_id)
        consumers_list = [lbl.value for lbl in deployment.labels
                          if lbl.key == 'csys-consumer-id']
        if prop == 'ids':
            return consumers_list
        if prop == 'count':
            return len(consumers_list)
        if prop == 'names':
            consumer_deployments = self.sm.list(
                Deployment, filters={'id': consumers_list},
                get_all_results=True)
            return [d.display_name for d in consumer_deployments]
        raise FunctionsEvaluationError(
            f'get_consumers has no property {prop}')

    def _normalize_group_cap_element_id(self, element_ids):
        get_with_ids = False
        if not isinstance(element_ids, list):
            if element_ids.startswith('deployment_id:'):
                get_with_ids = True
                element_ids = element_ids[len('deployment_id:'):]
            element_ids = [element_ids]
        return get_with_ids, element_ids

    def _get_deployment_group_caps(self, dep, element_ids, capability_path):
        if all(cap_id not in dep.capabilities for cap_id in element_ids):
            raise ValueError(dep.id)

        cap_values = []
        for cap_id in element_ids:
            try:
                cap = self._get_capability_by_path(
                    dep.capabilities[cap_id]['value'], capability_path)
            except KeyError:
                cap = None
            cap_values.append(cap)

        if len(cap_values) == 1:
            return cap_values[0]
        return cap_values

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

    def get_environment_capability(self, capability_path):
        # Represent the shared deployment
        label_value = self.get_label('csys-obj-parent', 0)
        # Represent the capability path
        capability_path = [label_value] + capability_path
        return self.get_capability(capability_path)

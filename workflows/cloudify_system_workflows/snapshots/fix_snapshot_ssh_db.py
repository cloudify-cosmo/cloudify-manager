########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
from __future__ import print_function


import os
import argparse

from manager_rest import flask_utils, config
from manager_rest.storage.models import Deployment
from manager_rest.storage import get_storage_manager

# These vars need to be loaded before the rest server is imported
# We're not currently sourcing anything else (such as rest port) to avoid
# unexpected extra interactions with them.
os.environ["MANAGER_REST_CONFIG_PATH"] = (
    "/opt/manager/cloudify-rest.conf"
)
os.environ["MANAGER_REST_SECURITY_CONFIG_PATH"] = (
    "/opt/manager/rest-security.conf"
)


def replace_ssh_keys(input_dict, original_string, secret_name):
    """
        Replace each SSH key path entry (original_string) in the top level of
        a dict with the secret.
    """
    changed = False
    for k in input_dict:
        if input_dict[k] == original_string:
            input_dict[k] = {'get_secret': secret_name}
            changed = True
    return changed


def update_agent_properties(input_dict, original_string, secret_name):
    """
        Replace any agent configuration SSH key settings in a provided dict.
    """
    changed = False
    for agent_config_key in ('agent_config', 'cloudify_agent'):
        if agent_config_key in input_dict:
            key = input_dict[agent_config_key].get('key')
            if key == original_string:
                input_dict[agent_config_key]['key'] = {
                    'get_secret': secret_name,
                }
                changed = True
    return changed


def fix_fabric_env(input_dict, original_string, secret_name):
    """
        Fix any fabric env in the provided dict. This will replace key paths
        to the specified path with keys pointing to the specified secret.
    """
    changed = False
    if 'fabric_env' in input_dict:
        if 'key_filename' in input_dict['fabric_env']:
            if input_dict['fabric_env']['key_filename'] == original_string:
                input_dict['fabric_env'].pop('key_filename')
                input_dict['fabric_env']['key'] = {
                    'get_secret': secret_name,
                }
                changed = True
    return changed


def main(original_string, secret_name):
    """
        For a given tenant, replace the SSH key path with the specified
        get_secret call in the top levels of all dicts where it is found.

        These replacements will occur in:
          - Deployment runtime properties (for agent configuration only).
          - Deployment operation inputs.
          - Deployment node properties (including agent configuration).
    """
    sm = get_storage_manager()

    res = sm.list(model_class=Deployment, get_all_results=True)
    for deployment in res:
        for node in deployment.nodes:
            for node_instance in node.instances:
                runtime_properties = node_instance.runtime_properties
                changed = update_agent_properties(runtime_properties,
                                                  original_string,
                                                  secret_name)
                if changed:
                    print('Changing runtime properties for `{0}`'.format(
                        node_instance.id
                    ))
                    sm.update(node_instance, modified_attrs=(
                        'runtime_properties',
                    ))
                    print('Updated')
                else:
                    print('No changes')

            ops = node.operations
            changed = False
            for op in ops:
                inputs = ops[op].get('inputs', {})
                key_changed = replace_ssh_keys(inputs,
                                               original_string,
                                               secret_name)
                fabric_changed = fix_fabric_env(inputs,
                                                original_string,
                                                secret_name)
                if key_changed or fabric_changed:
                    ops[op]['has_intrinsic_functions'] = True
                    changed = True
            props = node.properties
            new_changed = replace_ssh_keys(props,
                                           original_string,
                                           secret_name)
            changed = changed or new_changed
            new_changed = update_agent_properties(props,
                                                  original_string,
                                                  secret_name)
            changed = changed or new_changed
            if changed:
                print('Changing operations/properties for node '
                      '`{0}` on dep `{1}`'.format(node.id, deployment.id))
                sm.update(node, modified_attrs=(
                    'operations',
                    'properties',
                ))
                print('Updated')
            else:
                print('No changes')


def setup_flask_app(tenant_name):
    app = flask_utils.setup_flask_app()
    config.instance.load_configuration()
    flask_utils.set_admin_current_user(app)
    tenant = flask_utils.get_tenant_by_name(tenant_name)
    flask_utils.set_tenant_in_app(tenant)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=(
            "Replace SSH key paths with get_secret calls in a tenant's "
            "deployments and blueprint plans."
        )
    )

    parser.add_argument(
        'tenant',
        help='The name or ID of the tenant to be modified.',
    )
    parser.add_argument(
        'key_path',
        help='The old key path to be replaced.',
    )
    parser.add_argument(
        'secret_name',
        help='The secret containing the SSH private key file.',
    )

    args = parser.parse_args()

    tenant_name = args.tenant
    original_string = args.key_path
    secret_name = args.secret_name

    setup_flask_app(tenant_name)
    main(original_string, secret_name)

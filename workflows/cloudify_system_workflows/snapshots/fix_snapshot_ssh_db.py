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


import argparse
import os

import manager_rest.storage.storage_manager as stor
from manager_rest.storage.resource_models import (
    Deployment,
    Node,
    NodeInstance,
)
from manager_rest.storage.management_models import (
    Tenant,
)

# These vars need to be loaded before the rest server is imported
# We're not currently sourcing anything else (such as rest port) to avoid
# unexpected extra interactions with them.
os.environ["MANAGER_REST_CONFIG_PATH"] = (
    "/opt/manager/cloudify-rest.conf"
)
os.environ["MANAGER_REST_SECURITY_CONFIG_PATH"] = (
    "/opt/manager/rest-security.conf"
)

from manager_rest.server import app  # noqa


class FakeUser(object):
    is_authenticated = True
    is_active = True
    is_anonymous = False
    is_admin = True

    @staticmethod
    def get_id(*args, **kwargs):
        return '0'


class FakeTenant(object):
    id = 0


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


def commit_changes(storage_manager, item_class, item, update):
    """
        Commit changes to the DB for a given entity.
    """
    # Using the storage manager's update and refresh resulted in no updates
    storage_manager.db.session.query(item_class).filter_by(
        id=item.id,
    ).update(update)
    storage_manager.db.session.commit()
    storage_manager.db.session.refresh(item)


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
                input_dict['fabric_env'].pop('fabric_env')
                input_dict['fabric_env']['key'] = {
                    'get_secret': secret_name,
                }
                changed = True
    return changed


def main(tenant, original_string, secret_name):
    """
        For a given tenant, replace the SSH key path with the specified
        get_secret call in the top levels of all dicts where it is found.

        These replacements will occur in:
          - Deployment runtime properties (for agent configuration only).
          - Deployment operation inputs.
          - Deployment node properties (including agent configuration).
    """
    with app.app_context():
        sm = stor.SQLStorageManager()

        try:
            tenant_id = int(tenant)
        except ValueError:
            tenant_id = stor.db.session.query(Tenant).filter_by(
                name=tenant,
            ).one().id
        FakeTenant.id = tenant_id

        res = sm.list(model_class=Deployment)
        for deployment in res:
            for node in deployment.nodes:
                for node_instance in node.node_instances:
                    runtime_properties = node_instance.runtime_properties
                    changed = update_agent_properties(runtime_properties,
                                                      original_string,
                                                      secret_name)
                    if changed:
                        print('Changing runtime properties to: %s' % (
                            str(runtime_properties)
                        ))
                        commit_changes(
                            stor,
                            NodeInstance,
                            node_instance,
                            {'runtime_properties': runtime_properties},
                        )
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
                    changed = changed or key_changed or fabric_changed
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
                    print('Changing operations to: %s' % str(ops))
                    commit_changes(
                        stor,
                        Node,
                        node,
                        {'operations': ops, 'properties': props},
                    )
                    print('Updated')
                else:
                    print('No changes')


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

    tenant = args.tenant
    original_string = args.key_path
    secret_name = args.secret_name
    stor.current_user = FakeUser
    app.config['current_tenant'] = FakeTenant

    main(tenant, original_string, secret_name)

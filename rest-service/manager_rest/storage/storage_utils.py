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

from flask_security.utils import encrypt_password

from manager_rest import constants
from manager_rest.storage.models import Node
from manager_rest.storage.management_models import Tenant
from manager_rest.manager_exceptions import NotFoundError
from manager_rest.storage import user_datastore, db, get_storage_manager


def get_node(deployment_id, node_id):
    """Return the single node associated with a given ID and Dep ID
    """
    nodes = get_storage_manager().list(
        Node,
        filters={'deployment_id': deployment_id, 'id': node_id}
    )
    if not nodes:
        raise NotFoundError(
            'Requested Node with ID `{0}` on Deployment `{1}` '
            'was not found'.format(node_id, deployment_id)
        )
    return nodes[0]


def create_default_user_tenant_and_roles(admin_username, admin_password):
    """Create the bootstrap admin, the default tenant and the security roles

    :return: The default tenant
    """
    admin_role = _create_roles()
    default_tenant = _create_default_tenant()

    admin_user = user_datastore.create_user(
        id=constants.BOOTSTRAP_ADMIN_ID,
        username=admin_username,
        password=encrypt_password(admin_password),
        roles=[admin_role]
    )
    admin_user.tenants.append(default_tenant)
    user_datastore.commit()
    return default_tenant


def _create_roles():
    for role in constants.ALL_ROLES:
        user_datastore.find_or_create_role(name=role)
    return user_datastore.find_role(constants.ADMIN_ROLE)


def _create_default_tenant():
    default_tenant = Tenant(
        id=constants.DEFAULT_TENANT_ID,
        name=constants.DEFAULT_TENANT_NAME
    )
    db.session.add(default_tenant)
    return default_tenant

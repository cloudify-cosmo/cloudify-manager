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

from flask_security.utils import hash_password

from manager_rest import constants
from manager_rest.storage.models import Node
from manager_rest.storage import user_datastore, db, get_storage_manager
from manager_rest.manager_exceptions import NotFoundError
from manager_rest.storage.management_models import (
    Tenant, UserTenantAssoc, Role
)


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


def create_default_user_tenant_and_roles(admin_username,
                                         admin_password,
                                         amqp_manager,
                                         password_hash=None):
    """
    Create the bootstrap admin, the default tenant and the security roles,
    as well as a RabbitMQ vhost and user corresponding to the default tenant

    :return: The default tenant
    """
    sm = get_storage_manager()
    admin_role = sm.get(Role, None, filters={'name': 'sys_admin'})
    default_tenant = _create_default_tenant()
    amqp_manager.create_tenant_vhost_and_user(tenant=default_tenant)

    admin_user = user_datastore.create_user(
        id=constants.BOOTSTRAP_ADMIN_ID,
        username=admin_username,
        password=password_hash or hash_password(admin_password),
        roles=[admin_role]
    )

    # The admin user is assigned to the default tenant.
    # This is the default role when a user is added to a tenant.
    # Anyway, `sys_admin` will be the effective role since is the system role.
    user_role = user_datastore.find_role(constants.DEFAULT_TENANT_ROLE)
    user_tenant_association = UserTenantAssoc(
        user=admin_user,
        tenant=default_tenant,
        role=user_role,
    )
    admin_user.tenant_associations.append(user_tenant_association)
    user_datastore.commit()
    return default_tenant


def create_status_reporter_user_and_assign_role(username,
                                                password,
                                                role,
                                                user_id):
    """Creates a user and assigns its given role.
    """
    user = user_datastore.create_user(
        username=username,
        password=hash_password(password),
        roles=[role],
        id=user_id
    )

    default_tenant = Tenant.query.filter_by(
        id=constants.DEFAULT_TENANT_ID).first()
    reporter_role = user_datastore.find_role(role)
    if not reporter_role:
        raise NotFoundError("The username \"{0}\" cannot have the role \"{1}\""
                            " as the role doesn't exist"
                            "".format(username, role))
    user_tenant_association = UserTenantAssoc(
        user=user,
        tenant=default_tenant,
        role=reporter_role,
    )
    user.tenant_associations.append(user_tenant_association)
    user_datastore.commit()
    return user


def _create_default_tenant():
    default_tenant = Tenant(
        id=constants.DEFAULT_TENANT_ID,
        name=constants.DEFAULT_TENANT_NAME
    )
    db.session.add(default_tenant)
    return default_tenant


def try_acquire_lock_on_table(lock_number):
    # make sure a flask app exists before calling this function
    results = db.session.execute('SELECT pg_try_advisory_lock(:lock_number)',
                                 {'lock_number': lock_number})
    return results.first()[0]


def unlock_table(lock_number):
    # make sure a flask app exists before calling this function
    db.session.execute('SELECT pg_advisory_unlock(:lock_number)',
                       {'lock_number': lock_number})

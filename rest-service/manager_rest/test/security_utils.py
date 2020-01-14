#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

from cloudify.cluster_status import (
    DB_STATUS_REPORTER,
    BROKER_STATUS_REPORTER,
    MANAGER_STATUS_REPORTER,
    MANAGER_STATUS_REPORTER_ID,
    BROKER_STATUS_REPORTER_ID,
    DB_STATUS_REPORTER_ID
)

from manager_rest.storage.models import Tenant, UserTenantAssoc
from manager_rest.storage import user_datastore
from manager_rest.constants import (
    DEFAULT_TENANT_ID,
    DEFAULT_TENANT_ROLE,
)

ADMIN_ROLE = 'sys_admin'
USER_ROLE = 'default'
USER_IN_TENANT_ROLE = 'user'


def get_admin_user():
    return {
        'username': 'admin',
        'password': 'admin',
        'role': ADMIN_ROLE
    }


def get_status_reporters():
    return [
        {
            'username': MANAGER_STATUS_REPORTER,
            'password': 'password',
            'role': MANAGER_STATUS_REPORTER,
            'id': MANAGER_STATUS_REPORTER_ID
        },
        {
            'username': BROKER_STATUS_REPORTER,
            'password': 'password',
            'role': BROKER_STATUS_REPORTER,
            'id': BROKER_STATUS_REPORTER_ID
        },
        {
            'username': DB_STATUS_REPORTER,
            'password': 'password',
            'role': DB_STATUS_REPORTER,
            'id': DB_STATUS_REPORTER_ID
        },
    ]


def get_test_users():
    test_users = [
        {
            'username': 'alice',
            'password': 'alice_password',
            'role': ADMIN_ROLE
        },
        {
            'username': 'bob',
            'password': 'bob_password',
            'role': USER_ROLE
        },
        {
            'username': 'clair',
            'password': 'clair_password',
            'role': USER_ROLE,
            'active': False
        },
        {
            'username': 'dave',
            'password': 'dave_password',
            'role': USER_ROLE
        }
    ]
    return test_users


def add_users_to_db(user_list):
    default_tenant = Tenant.query.get(DEFAULT_TENANT_ID)
    for user in user_list:
        role = user_datastore.find_role(user['role'])
        user_obj = user_datastore.create_user(
            username=user['username'],
            password=hash_password(user['password']),
            roles=[role]
        )

        default_tenant_role = user_datastore.find_role(DEFAULT_TENANT_ROLE)
        user_obj.active = user.get('active', True)
        user_tenant_association = UserTenantAssoc(
            user=user_obj,
            tenant=default_tenant,
            role=default_tenant_role,
        )
        user_obj.tenant_associations.append(user_tenant_association)
    user_datastore.commit()

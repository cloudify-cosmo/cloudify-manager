#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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
#

from flask_restful import fields
from flask_restful_swagger import swagger


@swagger.model
class BaseResponse(object):
    resource_fields = {}


class ResourceID(BaseResponse):
    resource_fields = {
        'resource_id': fields.String
    }

    def __init__(self, **kwargs):
        self.resource_id = kwargs.get('resource_id')


class SecretsListResponse(BaseResponse):
    resource_fields = {
        'key': fields.String,
        'created_at': fields.String,
        'updated_at': fields.String,
        'resource_availability': fields.String,
        'visibility': fields.String,
        'tenant_name': fields.String,
        'created_by': fields.String,
        'is_hidden_value': fields.Boolean,
    }

    def __init__(self, **kwargs):
        self.key = kwargs.get('key')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
        self.resource_availability = kwargs.get('resource_availability')
        self.visibility = kwargs.get('visibility')
        self.tenant_name = kwargs.get('tenant_name')
        self.created_by = kwargs.get('created_by')
        self.is_hidden_value = kwargs.get('is_hidden_value')


@swagger.model
class UserResponse(object):

    resource_fields = {
        'username': fields.String,
        'tenants': fields.Raw,
        'tenant_roles': fields.Raw,
        'groups': fields.Raw,
        'role': fields.String,
        'group_system_roles': fields.Raw,
        'active': fields.Boolean,
        'last_login_at': fields.String,
        'is_locked': fields.Boolean
    }

    def __init__(self, **kwargs):
        self.username = kwargs.get('username')
        self.tenants = kwargs.get('tenants')
        self.tenant_roles = kwargs.get('tenant_roles')
        self.groups = kwargs.get('groups')
        self.role = kwargs.get('role')
        self.group_system_roles = kwargs.get('group_system_roles')
        self.active = kwargs.get('active')
        self.last_login_at = kwargs.get('last_login_at')
        self.is_locked = kwargs.get('is_locked')


@swagger.model
class TenantResponse(object):

    resource_fields = {
        'name': fields.String,
        'groups': fields.Raw,
        'users': fields.Raw,
        'user_roles': fields.Raw,
    }

    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        self.groups = kwargs.get('groups')
        self.users = kwargs.get('users')
        self.user_roles = kwargs.get('user_roles')

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


class BaseResponse(object):
    resource_fields = {}

    def __init__(self, **kwargs):
        for name in self.resource_fields:
            setattr(self, name, kwargs.get(name))


@swagger.model
class ResourceID(BaseResponse):
    resource_fields = {
        'resource_id': fields.String
    }


@swagger.model
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


@swagger.model
class UserResponse(BaseResponse):

    resource_fields = {
        'username': fields.String,
        'tenants': fields.Raw,
        'tenant_roles': fields.Raw,
        'groups': fields.Raw,
        'role': fields.String,
        'group_system_roles': fields.Raw,
        'active': fields.Boolean,
        'first_login_at': fields.String,
        'last_login_at': fields.String,
        'is_locked': fields.Boolean,
        'show_getting_started': fields.Boolean,
        'password_hash': fields.String,
    }


@swagger.model
class TenantResponse(BaseResponse):

    resource_fields = {
        'name': fields.String,
        'groups': fields.Raw,
        'users': fields.Raw,
        'user_roles': fields.Raw
    }


@swagger.model
class TenantDetailsResponse(BaseResponse):

    resource_fields = {
        'name': fields.String,
        'groups': fields.Raw,
        'users': fields.Raw,
        'user_roles': fields.Raw,
        'rabbitmq_username': fields.String,
        'rabbitmq_password': fields.String,
        'rabbitmq_vhost': fields.String,
    }


@swagger.model
class AgentResponse(BaseResponse):
    resource_fields = {
        'id': fields.String,
        'host_id': fields.String,
        'ip': fields.String,
        'install_method': fields.String,
        'system': fields.String,
        'version': fields.String,
        'node': fields.String,
        'deployment': fields.String,
        'tenant_name': fields.String
    }


@swagger.model
class DeploymentCapabilities(BaseResponse):

    resource_fields = {
        'deployment_id': fields.String,
        'capabilities': fields.Raw
    }


@swagger.model
class OperationResponse(BaseResponse):
    resource_fields = {
        'id': fields.String,
        'name': fields.String,
        'state': fields.String,
    }


@swagger.model
class License(BaseResponse):
    resource_fields = {
        'customer_id': fields.String,
        'expiration_date': fields.String,
        'license_edition': fields.String,
        'trial': fields.Boolean,
        'cloudify_version': fields.String,
        'capabilities': fields.Raw,
        'expired': fields.Boolean
    }


@swagger.model
class ItemsCount(BaseResponse):
    resource_fields = {
        'count': fields.Integer
    }


@swagger.model
class PermissionResponse(BaseResponse):
    resource_fields = {
        'role': fields.String,
        'permission': fields.String
    }

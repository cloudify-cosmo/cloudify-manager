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
        'permission': fields.String,
        'tenant_name': fields.String,
        'created_by': fields.String
    }

    def __init__(self, **kwargs):
        self.key = kwargs.get('key')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
        self.permission = kwargs.get('permission')
        self.tenant_name = kwargs.get('tenant_name')
        self.created_by = kwargs.get('created_by')

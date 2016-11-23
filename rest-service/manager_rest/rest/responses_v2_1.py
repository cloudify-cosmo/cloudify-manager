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

from flask_restful import fields
from flask_restful_swagger import swagger


@swagger.model
class MaintenanceMode(object):
    resource_fields = {
        'status': fields.String,
        'activated_at': fields.String,
        'activation_requested_at': fields.String,
        'remaining_executions': fields.Raw,
        'requested_by': fields.String
    }

    def __init__(self, **kwargs):
        self.status = kwargs.get('status')
        self.activated_at = kwargs.get('activated_at')
        self.activation_requested_at = kwargs.get('activation_requested_at')
        self.remaining_executions = kwargs.get('remaining_executions')
        self.requested_by = kwargs.get('requested_by')

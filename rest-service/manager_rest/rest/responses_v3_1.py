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

from .responses_v3 import BaseResponse


@swagger.model
class LogEvent(BaseResponse):
    resource_fields = {
        'timestamp': fields.String,
        'reported_timestamp': fields.String,
        'message': fields.String,
        'message_code': fields.String,
        'operation': fields.String,
        'node_id': fields.String,
        'node_name': fields.String,
        'workflow_id': fields.String,
        'node_instance_id': fields.String,
        'source_id': fields.String,
        'target_id': fields.String,
        'execution_id': fields.String,
        'deployment_id': fields.String,
        'error_causes': fields.Raw,
        'level': fields.String,
        'type': fields.String,
        'event_type': fields.String,
    }

#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from flask.ext.restful import fields
from flask_restful_swagger import swagger

from manager_rest.responses import (BlueprintState as BlueprintStateV1,  # NOQA
                                    Execution,
                                    Deployment,
                                    DeploymentModification,
                                    Node,
                                    NodeInstance)


@swagger.model
class BlueprintState(BlueprintStateV1):

    resource_fields = dict(BlueprintStateV1.resource_fields.items() + {
        'description': fields.String,
    }.items())

    def __init__(self, **kwargs):
        super(BlueprintState, self).__init__(**kwargs)
        self.description = kwargs['description']


@swagger.model
class Snapshot(object):

    resource_fields = {
        'id': fields.String,
        'created_at': fields.String,
        'status': fields.String,
        'error': fields.String
    }

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.created_at = kwargs['created_at']
        self.status = kwargs['status']
        self.error = kwargs['error']

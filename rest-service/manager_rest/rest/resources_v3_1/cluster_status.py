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

import pydantic
from typing import Optional

from flask import request

from cloudify.cluster_status import ServiceStatus

from manager_rest.rest import responses, swagger
from manager_rest.security.authorization import authorize
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.security import SecuredResource
from manager_rest.cluster_status_manager import (STATUS,
                                                 get_cluster_status)


class _ClusterStatusQuery(pydantic.BaseModel):
    summary: Optional[bool] = False


class ClusterStatus(SecuredResource):
    @swagger.operation(
        responseClass=responses.Status,
        nickname="cluster-status",
        notes="Returns state of the Cloudify cluster"
    )
    @authorize('cluster_status_get')
    @marshal_with(responses.Status)
    def get(self):
        """Get the status of the entire cloudify cluster"""
        args = _ClusterStatusQuery.parse_obj(request.args)
        summary_response = args.summary
        cluster_status = get_cluster_status(detailed=not summary_response)

        # If the response should be only the summary
        if summary_response:
            short_status = cluster_status.get(STATUS)
            status_code = 500 if short_status == ServiceStatus.FAIL else 200
            return {'status': short_status, 'services': {}}, status_code

        return cluster_status

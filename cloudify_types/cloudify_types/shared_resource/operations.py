# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from cloudify.decorators import operation

from cloudify_types.utils import proxy_operation

from .shared_resource import SharedResource
from .constants import WORKFLOW_EXECUTION_TIMEOUT
from .execute_shared_resource_workflow import execute_shared_resource_workflow


@operation(resumable=True)
@proxy_operation('validate_deployment')
def connect_deployment(operation, **_):
    return getattr(SharedResource(_), operation)()


@operation(resumable=True)
@proxy_operation('remove_inter_deployment_dependency')
def disconnect_deployment(operation, **_):
    return getattr(SharedResource(_), operation)()


@operation(resumable=True)
def execute_workflow(workflow_id,
                     parameters,
                     timeout=WORKFLOW_EXECUTION_TIMEOUT,
                     redirect_logs=True,
                     **_):
    return execute_shared_resource_workflow(workflow_id,
                                            parameters,
                                            timeout,
                                            redirect_logs)

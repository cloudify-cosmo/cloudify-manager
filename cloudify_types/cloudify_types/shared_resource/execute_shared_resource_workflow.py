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

from cloudify import ctx, manager
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.client import CloudifyClient

from cloudify_types.component.utils import (
    populate_runtime_with_wf_results)
from cloudify_types.component.polling import (poll_with_timeout,
                                              is_all_executions_finished,
                                              verify_execution_state)

from .constants import SHARED_RESOURCE_TYPE


def _verify_shared_resource_node():
    return ctx.target.node.type == SHARED_RESOURCE_TYPE


def _get_target_shared_resource_client():
    return ctx.target.node.properties.get('client', {})


def execute_shared_resource_workflow(workflow_id,
                                     parameters,
                                     wf_timeout,
                                     redirect_logs):
    if not _verify_shared_resource_node():
        raise NonRecoverableError(
          f'Tried to execute "{workflow_id}" workflow on a non '
          f'SharedResource node "{ctx.target.node.id}"')

    ctx.logger.info("Setting up required input for executing workflow on"
                    "a SharedResource.")
    # Cloudify client setup
    client_config = _get_target_shared_resource_client()
    if client_config:
        http_client = CloudifyClient(client_config)
    else:
        http_client = manager.get_rest_client()

    target_deployment_id = (ctx.target.node
                            .properties['resource_config']
                            ['deployment']['id'])

    # Wait for the deployment to finish any executions
    ctx.logger.info('Waiting until all currently running executions on "%s" '
                    'SharedResource deployment finish.', target_deployment_id)
    if not poll_with_timeout(lambda:
                             is_all_executions_finished(
                                 http_client, target_deployment_id),
                             timeout=wf_timeout,
                             expected_result=True):
        return ctx.operation.retry(
            f'The "{target_deployment_id}" deployment is not ready for '
            f'workflow execution.')

    ctx.logger.info('Starting execution of "%s" workflow for "%s" '
                    'SharedResource deployment',
                    workflow_id, target_deployment_id)
    execution = http_client.executions.start(
        deployment_id=target_deployment_id,
        workflow_id=workflow_id,
        parameters=parameters,
        allow_custom_parameters=True)
    ctx.logger.debug('Execution for "%s" on "%s" deployment response is: %s',
                     workflow_id, target_deployment_id, execution)

    execution_id = execution['id']
    if not verify_execution_state(http_client,
                                  execution_id,
                                  target_deployment_id,
                                  redirect_logs,
                                  workflow_state='terminated',
                                  instance_ctx=ctx.target.instance):
        raise NonRecoverableError(
            f'Execution "{execution_id}" failed for '
            f'"{target_deployment_id}" deployment.')

    ctx.logger.info('Execution succeeded for "%s" SharedResource '
                    'deployment of "%s" workflow',
                    target_deployment_id, workflow_id)
    populate_runtime_with_wf_results(http_client,
                                     target_deployment_id,
                                     ctx.target.instance)
    return True

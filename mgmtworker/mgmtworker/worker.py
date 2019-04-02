########
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
############

import argparse
import logging

from cloudify import dispatch
from cloudify.logs import setup_agent_logger
from cloudify.utils import get_admin_api_token
from cloudify.constants import MGMTWORKER_QUEUE
from cloudify.models_states import ExecutionState
from cloudify.state import current_workflow_ctx, workflow_ctx
from cloudify.manager import get_rest_client, update_execution_status
from cloudify.amqp_client import AMQPConnection, get_client, SendHandler

from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import InvalidExecutionUpdateStatus

from cloudify_agent.worker import (
    ProcessRegistry,
    CloudifyOperationConsumer,
    ServiceTaskConsumer
)

from .hooks import HookConsumer


DEFAULT_MAX_WORKERS = 10
logger = logging.getLogger('mgmtworker')


class CloudifyWorkflowConsumer(CloudifyOperationConsumer):
    routing_key = 'workflow'
    handler = dispatch.WorkflowHandler
    late_ack = True

    def handle_task(self, full_task):
        if self.is_scheduled_execution(full_task):
            task = full_task['cloudify_task']
            ctx = task['kwargs']['__cloudify_context']
            self.handle_scheduled_execution(ctx['execution_id'])

            if not self.can_scheduled_execution_start(ctx['execution_id'],
                                                      ctx['tenant']['name']):
                # Execution can't currently start running, it has been queued.
                return
        return super(CloudifyWorkflowConsumer, self).handle_task(full_task)

    @staticmethod
    def is_scheduled_execution(full_task):
        """
        If a task contains a `dead-letter-exchange` (dlx_id) information it
        means it was scheduled
        """
        return True if full_task.get('dlx_id') else False

    def handle_scheduled_execution(self, execution_id):
        # This is a scheduled task. It was sent to mgmtworker queue from a
        # temp queue using a dead-letter-exchange (dlx), need to delete them
        self.delete_queue(execution_id + '_queue')
        self.delete_exchange(execution_id)

    @staticmethod
    def can_scheduled_execution_start(execution_id, tenant):
        """
        This method checks whether or not a scheduled execution can currently
        start running. If it can't - it changes the executions status to
        QUEUED (so that it will automatically start running when possible)
        """
        api_token = get_admin_api_token()
        tenant_client = get_rest_client(tenant=tenant, api_token=api_token)
        if tenant_client.executions.should_start(execution_id):
            return True

        tenant_client.executions.update(execution_id, ExecutionState.QUEUED)
        return False


class MgmtworkerServiceTaskConsumer(ServiceTaskConsumer):
    """ServiceTaskConsumer with additional mgmtworker-only tasks"""

    service_tasks = ServiceTaskConsumer.service_tasks.copy()
    service_tasks['cancel-workflow'] = 'cancel_workflow_task'

    def __init__(self, *args, **kwargs):
        self._workflow_registry = kwargs.pop('workflow_registry')
        super(MgmtworkerServiceTaskConsumer, self).__init__(*args, **kwargs)

    def cancel_workflow_task(self, execution_id, rest_token, tenant,
                             execution_token):
        logger.info('Cancelling workflow {0}'.format(execution_id))

        class CancelCloudifyContext(object):
            """A CloudifyContext that has just enough data to cancel workflows
            """
            def __init__(self):
                self.tenant = tenant
                self.tenant_name = tenant['name']
                self.rest_token = rest_token
                self.execution_token = execution_token

        with current_workflow_ctx.push(CancelCloudifyContext()):
            self._workflow_registry.cancel(execution_id)
            self._cancel_agent_operations(execution_id)
            try:
                update_execution_status(execution_id, Execution.CANCELLED)
            except InvalidExecutionUpdateStatus:
                # the workflow process might have cleaned up, and marked the
                # workflow failed or cancelled already
                logger.info('Failed to update execution status: {0}'
                            .format(execution_id))

    def _cancel_agent_operations(self, execution_id):
        """Send a cancel-operation task to all agents for this deployment"""
        rest_client = get_rest_client()
        for target in self._get_agents(rest_client, execution_id):
            self._send_cancel_task(target, execution_id)

    def _send_cancel_task(self, target, execution_id):
        """Send a cancel-operation task to the agent given by `target`"""
        message = {
            'service_task': {
                'task_name': 'cancel-operation',
                'kwargs': {'execution_id': execution_id}
            }
        }
        if target == MGMTWORKER_QUEUE:
            client = get_client()
        else:
            tenant = workflow_ctx.tenant
            client = get_client(
                amqp_user=tenant['rabbitmq_username'],
                amqp_pass=tenant['rabbitmq_password'],
                amqp_vhost=tenant['rabbitmq_vhost']
            )

        handler = SendHandler(exchange=target, routing_key='service')
        client.add_handler(handler)
        with client:
            handler.publish(message)

    def _get_agents(self, rest_client, execution_id):
        """Get exchange names for agents related to this execution.

        Note that mgmtworker is related to all executions, since every
        execution might have a central_deployment_agent operation.
        """
        yield MGMTWORKER_QUEUE
        execution = rest_client.executions.get(execution_id)
        node_instances = rest_client.node_instances.list(
            deployment_id=execution.deployment_id,
            _get_all_results=True)
        for instance in node_instances:
            if self._is_agent(instance):
                yield instance.runtime_properties['cloudify_agent']['queue']

    def _is_agent(self, node_instance):
        """Does the node_instance have an agent?"""
        # Compute nodes are hosts, so checking if host_id is the same as id
        # is a way to check if the node instance is a Compute without
        # querying for the actual Node
        is_compute = node_instance.id == node_instance.host_id
        return (is_compute and
                'cloudify_agent' in node_instance.runtime_properties)


def make_amqp_worker(args):
    operation_registry = ProcessRegistry()
    workflow_registry = ProcessRegistry()
    handlers = [
        CloudifyOperationConsumer(args.queue, args.max_workers,
                                  registry=operation_registry),
        CloudifyWorkflowConsumer(args.queue, args.max_workers,
                                 registry=workflow_registry),
        MgmtworkerServiceTaskConsumer(args.name, args.queue, args.max_workers,
                                      operation_registry=operation_registry,
                                      workflow_registry=workflow_registry),
    ]

    if args.hooks_queue:
        handlers.append(HookConsumer(args.hooks_queue,
                                     registry=operation_registry,
                                     max_workers=args.max_workers))

    return AMQPConnection(handlers=handlers, connect_timeout=None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue')
    parser.add_argument('--max-workers', default=DEFAULT_MAX_WORKERS, type=int)
    parser.add_argument('--name')
    parser.add_argument('--hooks-queue')
    args = parser.parse_args()

    setup_agent_logger('mgmtworker')

    worker = make_amqp_worker(args)
    worker.consume()


if __name__ == '__main__':
    main()

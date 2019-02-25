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

from cloudify_rest_client.exceptions import (
    CloudifyClientError,
)

from cloudify.logs import setup_agent_logger
from cloudify.models_states import ExecutionState
from cloudify.manager import get_rest_client

from cloudify.utils import get_admin_api_token
from cloudify.amqp_client import AMQPConnection
from cloudify_agent.worker import (
    ProcessRegistry,
    CloudifyOperationConsumer,
    CloudifyWorkflowConsumer,
    ServiceTaskConsumer,
    HookConsumer,
    _setup_logger as _setup_cloudify_agent_logger
)

DEFAULT_MAX_WORKERS = 10
logger = None


def _setup_logger():
    global logger
    setup_agent_logger('mgmtworker')
    logger = logging.getLogger('mgmtworker')


def _resume_stuck_executions():
    """Resume executions that were in the STARTED state.

    This runs after the mgmtworker has started, and will find and resume
    all executions that are in the STARTED state, which would otherwise
    become stuck.

    For every tenant, query the executions, and for every execution in
    STARTED state, resume it.

    This uses the admin token.
    """
    admin_api_token = get_admin_api_token()
    rest_client = get_rest_client(tenant='default_tenant',
                                  api_token=admin_api_token)
    tenants = rest_client.tenants.list()
    for tenant in tenants:
        tenant_client = get_rest_client(tenant=tenant.name,
                                        api_token=admin_api_token)
        for execution in tenant_client.executions.list(
                status=ExecutionState.STARTED):
            try:
                tenant_client.executions.resume(execution.id)
            except CloudifyClientError as e:
                logger.warning('Could not resume execution {0} on '
                               'tenant {1}: {2}'
                               .format(execution.id, tenant.name, e))
            else:
                logger.info('Resuming execution {0} on tenant {1}'
                            .format(execution.id, tenant.name))


def make_amqp_worker(args):
    operation_registry = ProcessRegistry()
    workflow_registry = ProcessRegistry()
    handlers = [
        CloudifyOperationConsumer(args.queue, args.max_workers,
                                  registry=operation_registry),
        CloudifyWorkflowConsumer(args.queue, args.max_workers,
                                 registry=workflow_registry),
        ServiceTaskConsumer(args.name, args.queue, args.max_workers,
                            operation_registry=operation_registry,
                            workflow_registry=workflow_registry),
    ]

    if args.hooks_queue:
        handlers.append(HookConsumer(args.hooks_queue))

    return AMQPConnection(handlers=handlers, connect_timeout=None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue')
    parser.add_argument('--max-workers', default=DEFAULT_MAX_WORKERS, type=int)
    parser.add_argument('--name')
    parser.add_argument('--hooks-queue')
    args = parser.parse_args()

    _setup_logger()
    _setup_cloudify_agent_logger('mgmtworker')
    _resume_stuck_executions()

    worker = make_amqp_worker(args)
    worker.consume()


if __name__ == '__main__':
    main()

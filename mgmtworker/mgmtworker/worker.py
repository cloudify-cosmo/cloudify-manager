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

from cloudify.logs import setup_agent_logger

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

    _setup_logger()
    _setup_cloudify_agent_logger('mgmtworker')

    worker = make_amqp_worker(args)
    worker.consume()


if __name__ == '__main__':
    main()

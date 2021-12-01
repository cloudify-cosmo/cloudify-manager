import os
import sys
import json
import time
import shutil
import subprocess
import logging
import argparse
from contextlib import contextmanager

from cloudify import broker_config
from cloudify.logs import setup_agent_logger
from cloudify.utils import get_admin_api_token, get_tenant
from cloudify.constants import MGMTWORKER_QUEUE
from cloudify.models_states import ExecutionState
from cloudify.state import current_workflow_ctx
from cloudify.manager import get_rest_client, update_execution_status
from cloudify.amqp_client import AMQPConnection, get_client, SendHandler

from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import InvalidExecutionUpdateStatus

from cloudify_agent.worker import (
    ProcessRegistry,
    ServiceTaskConsumer,
    CloudifyOperationConsumer
)
from cloudify_agent import worker as agent_worker

from .hooks import HookConsumer
from .monitoring import (
    get_broker_hosts,
    get_db_hosts,
    get_manager_hosts,
    update_broker_targets,
    update_broker_alerts,
    update_db_targets,
    update_db_alerts,
    update_manager_targets,
    update_manager_alerts,
)
try:
    from cloudify_premium import syncthing_utils
except ImportError:
    syncthing_utils = None

DEFAULT_MAX_WORKERS = 10
logger = logging.getLogger('mgmtworker')


class MgmtworkerOperationConsumer(CloudifyOperationConsumer):
    """CloudifyOperationConsumer but with late_ack enabled.

    late_ack means that operations are acked after they're finished, so
    if one mgmtworker dies while handling an operation, the operation
    will be re-sent to another mgmtworker.
    """
    late_ack = True


class CloudifyWorkflowConsumer(CloudifyOperationConsumer):
    routing_key = 'workflow'
    late_ack = True

    @contextmanager
    def _update_operation_state(self, *args, **kwargs):
        # noop - override superclass method, which tries to update the
        # operation state: we're not working with operations, but workflows
        yield

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
        return full_task.get('dlx_id')

    def handle_scheduled_execution(self, execution_id):
        # This is a scheduled task. It was sent to mgmtworker queue from a
        # temp queue using a dead-letter-exchange (dlx), need to delete them
        self.delete_queue(execution_id + '_queue')
        self.delete_exchange(execution_id)

    @staticmethod
    def can_scheduled_execution_start(execution_id, tenant):
        """
        This method checks if a scheduled execution can currently start. If it
        wasn't cancelled but can't currently start - it changes the executions
        status to QUEUED (so it will automatically start when possible).
        """
        api_token = get_admin_api_token()
        tenant_client = get_rest_client(tenant=tenant, api_token=api_token)
        execution = tenant_client.executions.get(execution_id)
        if execution['status'] == ExecutionState.CANCELLED:
            return False
        if tenant_client.executions.should_start(execution_id):
            return True

        tenant_client.executions.update(execution_id, ExecutionState.QUEUED)
        return False


class MgmtworkerServiceTaskConsumer(ServiceTaskConsumer):
    """ServiceTaskConsumer with additional mgmtworker-only tasks"""

    service_tasks = ServiceTaskConsumer.service_tasks.copy()
    service_tasks['cancel-workflow'] = 'cancel_workflow_task'
    service_tasks['delete-source-plugins'] = 'delete_source_plugins_task'
    service_tasks['manager-added'] = 'manager_added'
    service_tasks['manager-removed'] = 'manager_removed'
    service_tasks['broker-added'] = 'broker_added'
    service_tasks['broker-updated'] = 'broker_updated'
    service_tasks['broker-removed'] = 'broker_removed'
    service_tasks['db-updated'] = 'db_updated'
    service_tasks['restart-restservice'] = 'restart_restservice'
    service_tasks['clean-tenant-dirs'] = 'clean_tenant_dirs'

    def __init__(self, *args, **kwargs):
        self._workflow_registry = kwargs.pop('workflow_registry')
        name = os.environ['MANAGER_NAME']
        queue_name = 'cloudify-mgmtworker-service-{0}'.format(name)
        kwargs['exchange_type'] = 'fanout'
        super(MgmtworkerServiceTaskConsumer, self).__init__(
            name, queue_name, *args, **kwargs)
        self.exchange = 'cloudify-mgmtworker-service'

    def clean_tenant_dirs(self, tenant_name):
        if not tenant_name:
            logger.error('Clean tenant dirs called with empty tenant name')
            return

        logger.info('Cleaning directories for tenant %s', tenant_name)

        paths = [
            '/opt/mgmtworker/env/plugins/{tenant}',
            '/opt/manager/resources/blueprints/{tenant}',
            '/opt/manager/resources/uploaded-blueprints/{tenant}',
            '/opt/manager/resources/deployments/{tenant}',
        ]

        for path in paths:
            full_path = path.format(tenant=tenant_name)
            logger.info('Purging %s', full_path)
            shutil.rmtree(full_path, ignore_errors=True)

    def restart_restservice(self, service_management):
        logger.info('Restarting restservice.')

        service_command = 'systemctl'
        if service_management == 'supervisord':
            service_command = 'supervisorctl'

        subprocess.check_call([
            'sudo', service_command, 'restart', 'cloudify-restservice',
        ])

    def manager_added(self):
        logger.info('A manager has been added to the cluster, updating '
                    'Cluster (Syncthing and Monitoring)')
        rest_client = get_rest_client(
            tenant='default_tenant',
            api_token=get_admin_api_token()
        )
        syncthing_utils.mgmtworker_update_devices(rest_client=rest_client)
        manager_hosts = list(get_manager_hosts(rest_client.manager))
        update_manager_targets(manager_hosts)
        update_manager_alerts(manager_hosts)

    def manager_removed(self):
        logger.info('A manager has been removed from the cluster, updating '
                    'Cluster (Syncthing and Monitoring)')
        rest_client = get_rest_client(
            tenant='default_tenant',
            api_token=get_admin_api_token()
        )
        syncthing_utils.mgmtworker_update_devices(rest_client=rest_client)
        manager_hosts = list(get_manager_hosts(rest_client.manager))
        update_manager_targets(manager_hosts)
        update_manager_alerts(manager_hosts)

    def broker_added(self):
        logger.info('A broker has been added to the cluster, '
                    'updating cluster monitoring')
        rest_client = get_rest_client(
            tenant='default_tenant',
            api_token=get_admin_api_token()
        )
        broker_hosts = list(get_broker_hosts(rest_client.manager))
        update_broker_targets(broker_hosts)
        update_broker_alerts(broker_hosts)

    def broker_updated(self):
        logger.info('A broker has been updated in the cluster, '
                    'updating cluster monitoring')
        rest_client = get_rest_client(
            tenant='default_tenant',
            api_token=get_admin_api_token()
        )
        broker_hosts = list(get_broker_hosts(rest_client.manager))
        update_broker_targets(broker_hosts)
        update_broker_alerts(broker_hosts)

    def broker_removed(self):
        logger.info('A broker has been removed from the cluster, '
                    'updating cluster monitoring')
        rest_client = get_rest_client(
            tenant='default_tenant',
            api_token=get_admin_api_token()
        )
        broker_hosts = list(get_broker_hosts(rest_client.manager))
        update_broker_targets(broker_hosts)
        update_broker_alerts(broker_hosts)

    def db_updated(self):
        logger.info('DB nodes were updated in the cluster, '
                    'updating cluster monitoring')
        rest_client = get_rest_client(
            tenant='default_tenant',
            api_token=get_admin_api_token()
        )
        db_hosts = list(get_db_hosts(rest_client.manager))
        update_db_targets(db_hosts)
        update_db_alerts(db_hosts)

    def delete_source_plugins_task(self, deployment_id, tenant_name):
        dep_dir = os.path.join(sys.prefix, 'source_plugins',
                               tenant_name, deployment_id)
        shutil.rmtree(dep_dir, ignore_errors=True)

    def cancel_workflow_task(self, execution_ids, rest_token, tenant,
                             rest_host):
        logger.info('Cancelling workflows {0}'.format(execution_ids))

        class CancelCloudifyContext(object):
            """A CloudifyContext that has just enough data to cancel workflows
            """
            def __init__(self):
                self.rest_host = rest_host
                self.tenant_name = tenant['name']
                self.rest_token = rest_token
                self.execution_token = None
                # always bypass - this is a kill, as forceful as we can get
                self.bypass_maintenance = True

        with current_workflow_ctx.push(CancelCloudifyContext()):
            for execution_id in execution_ids:
                self._workflow_registry.cancel(execution_id)
                self._cancel_agent_operations(execution_id)
                try:
                    update_execution_status(execution_id, Execution.CANCELLED)
                except InvalidExecutionUpdateStatus:
                    # the workflow process might have cleaned up, and marked
                    # the workflow failed or cancelled already
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
            tenant = get_tenant()
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
                try:
                    yield instance.runtime_properties[
                        'cloudify_agent']['queue']
                except KeyError:
                    pass

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
        MgmtworkerOperationConsumer(args.queue, args.max_workers,
                                    registry=operation_registry),
        CloudifyWorkflowConsumer(args.queue, args.max_workers,
                                 registry=workflow_registry),
        MgmtworkerServiceTaskConsumer(args.max_workers,
                                      operation_registry=operation_registry,
                                      workflow_registry=workflow_registry),
    ]

    if args.hooks_queue:
        handlers.append(HookConsumer(args.hooks_queue,
                                     registry=operation_registry,
                                     max_workers=args.max_workers))

    return AMQPConnection(handlers=handlers, connect_timeout=None)


def prepare_broker_config():
    client = get_rest_client(
        tenant='default_tenant', api_token=get_admin_api_token())
    brokers = client.manager.get_brokers().items
    config_path = broker_config.get_config_path()
    cert_path = os.path.join(os.path.dirname(config_path), 'broker_cert.pem')
    with open(cert_path, 'w') as f:
        f.write('\n'.join(broker.ca_cert_content for broker in brokers
                if broker.ca_cert_content))
    broker_addrs = [broker.networks.get('default') for broker in brokers
                    if broker.networks.get('default')]
    config = {
        'broker_ssl_enabled': True,
        'broker_cert_path': cert_path,
        'broker_username': brokers[0].username,
        'broker_password': brokers[0].password,
        'broker_vhost': '/',
        'broker_management_hostname': brokers[0].management_host,
        'broker_hostname': broker_addrs
    }
    with open(config_path, 'w') as f:
        json.dump(config, f)
    broker_config.load_broker_config()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue')
    parser.add_argument('--max-workers', default=DEFAULT_MAX_WORKERS, type=int)
    parser.add_argument('--hooks-queue')
    args = parser.parse_args()

    setup_agent_logger('mgmtworker')
    agent_worker.logger = logger

    while True:
        prepare_broker_config()
        worker = make_amqp_worker(args)
        try:
            worker.consume()
        except Exception:
            logger.exception('Error while reading from rabbitmq')
        time.sleep(1)


if __name__ == '__main__':
    main()

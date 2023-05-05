import asyncio
import json
from collections import defaultdict
from datetime import datetime
from queue import Queue
from threading import Event, Thread
from time import sleep

from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client import CloudifyClient

DEFAULT_HTTP_TIMEOUT_SECONDS = 10.0
WAIT_FOR_SNAPSHOT_ENTITIES_SECONDS = 0.1
RELATED_TABLES = {'executions', 'execution_groups', 'events', 'logs'}


class AuditLogListener(Thread):
    """AuditLogListener is a threaded wrapper for AuditLogAsyncClient.stream"""
    def __init__(
            self,
            client: CloudifyClient,
            queue: Queue,
            daemon=True,
            stream_timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
            **kwargs
    ):
        if not hasattr(client.auditlog, 'stream'):
            raise NonRecoverableError('Asynchronous client for audit_log has '
                                      'not been initialised.')
        super().__init__(daemon=daemon, **kwargs)
        self._client = client
        self._queue = queue
        self._loop = asyncio.new_event_loop()
        self._stopped = Event()
        self._tenant_clients: dict[str: CloudifyClient] = {}
        self._stream_timeout = stream_timeout
        self.__snapshot_entities: dict[tuple[str | None, str], set[str]] = \
            defaultdict(set)

    def start(self, tenant_clients: dict[str, CloudifyClient] | None = None):
        self._tenant_clients = tenant_clients or {}
        super().start()

    def run(self):
        self._loop.run_until_complete(self._stream_logs())

    def stop(self):
        self._stopped.set()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop.call_soon_threadsafe(self._loop.close)

    def append_entities(
            self,
            tenant_name: str | None,
            entity_type: str,
            identifiers: set[str],
    ):
        key = (tenant_name, entity_type)
        self.__snapshot_entities[key] = \
            self.__snapshot_entities[key].union(identifiers)

    async def _stream_logs(self):
        """Keep putting logs in a queue, reconnect in case of any errors."""
        since = datetime.now()

        while not self._stopped.is_set():
            try:
                if not self.__snapshot_entities:
                    sleep(WAIT_FOR_SNAPSHOT_ENTITIES_SECONDS)
                    continue
                response = await self._client.auditlog.stream(
                    timeout=self._stream_timeout, since=since)
                async for data in response.content:
                    for audit_log in _streamed_audit_log(data):
                        if self._ref_in_snapshot(audit_log) \
                                or self._related_to_snapshot(audit_log):
                            self._queue.put(audit_log)
                        since = audit_log.get('created_at')
            except BaseException:
                pass

    def _ref_in_snapshot(self, audit_log: dict) -> bool:
        ref_identifier = audit_log.get('ref_identifier', {})
        tenant_name = ref_identifier.get('tenant_name')
        ref_table = audit_log['ref_table']

        if (tenant_name, ref_table) not in self.__snapshot_entities:
            return False

        key_id = '_storage_id' if ref_table in ['events', 'logs'] else 'id'
        entity_id = ref_identifier.get(key_id, None)

        if entity_id:
            return (
                    entity_id in
                    self.__snapshot_entities[(tenant_name, ref_table)]
            )
        return False

    def _related_to_snapshot(self, audit_log: dict) -> bool:
        if audit_log['ref_table'] not in RELATED_TABLES:
            return False

        ref_identifier = audit_log.get('ref_identifier', {})
        client = self._tenant_clients[ref_identifier['tenant_name']]

        if audit_log['ref_table'] == 'executions':
            execution = client.executions.get(ref_identifier['id'])
            deployment_id = execution.deployment_id
            key = (ref_identifier['tenant_name'], 'deployments')
            return deployment_id in self.__snapshot_entities[key]

        if audit_log['ref_table'] == 'execution_groups':
            execution_group = client.execution_groups.get(ref_identifier['id'])
            deployment_group_id = execution_group.deployment_group_id
            key = (ref_identifier['tenant_name'], 'deployment_groups')
            return deployment_group_id in self.__snapshot_entities[key]

        # Since https://github.com/cloudify-cosmo/cloudify-manager/pull/3225
        # neither events nor logs with a valid execution_id are reported in
        # audit_log.  Hence, we will not try to figure out if modified rows
        # are related to the snapshot.

        return False


def _streamed_audit_log(data):
    line = data.strip().decode(errors='ignore')
    if line:
        yield json.loads(line)

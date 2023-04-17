import asyncio
import json
from collections import defaultdict
from datetime import datetime
from queue import Queue
from threading import Event, Thread

from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client import CloudifyClient


class AuditLogListener(Thread):
    """AuditLogListener is a threaded wrapper for AuditLogAsyncClient.stream"""
    def __init__(
            self,
            client: CloudifyClient,
            queue: Queue,
            daemon=True,
            **kwargs
    ):
        if not hasattr(client.auditlog, 'stream'):
            raise NonRecoverableError('Asynchronous client for audit_log has '
                                      'not been initialised.')
        super().__init__(daemon=daemon, **kwargs)
        self._client = client
        self._queue = queue
        self._loop = asyncio.new_event_loop()
        self.stopped = Event()
        self._tenant_clients = {}
        self._blueprints = defaultdict(list)
        self._plugins = defaultdict(list)

    def start(
            self,
            tenant_clients: dict[str, CloudifyClient] | None = None,
            blueprints: list[tuple[str, str]] | None = None,
            plugins: list[tuple[str, str]] | None = None,
    ):
        self._tenant_clients = tenant_clients
        if blueprints:
            for tenant_name, blueprint_id in blueprints:
                self._blueprints[tenant_name].append(blueprint_id)
        if plugins:
            for tenant_name, plugin_id in plugins:
                self._plugins[tenant_name].append(plugin_id)
        super().start()

    def run(self):
        self._loop.run_until_complete(self._stream_logs())

    def stop(self):
        self.stopped.set()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop.call_soon_threadsafe(self._loop.close)

    async def _stream_logs(self):
        """Keep putting logs in a queue, reconnect in case of any errors."""
        since = datetime.now()

        while not self.stopped.is_set():
            try:
                response = await self._client.auditlog.stream(since=since)
                async for data in response.content:
                    for audit_log in _streamed_audit_log(data):
                        if self._in_right_context(audit_log):
                            self._queue.put(audit_log)
                        since = audit_log.get('created_at')
            except Exception:
                pass

    def _in_right_context(self, audit_log: dict) -> bool:
        match audit_log['ref_table']:
            case 'blueprints':
                return self._blueprint_matches(audit_log)
            case 'deployments':
                return self._deployment_matches(audit_log)
            case _: return False

    def _blueprint_matches(self, audit_log: dict) -> bool:
        blueprint_id = audit_log['ref_identifier']['id']
        tenant_name = audit_log['ref_identifier']['tenant_name']
        return blueprint_id in self._blueprints[tenant_name]

    def _deployment_matches(self, audit_log: dict) -> bool:
        deployment_id = audit_log['ref_identifier']['id']
        tenant_name = audit_log['ref_identifier']['tenant_name']
        deployment = self._tenant_clients[tenant_name].deployments.get(
                deployment_id, all_sub_deployments=False)
        return deployment.blueprint_id in self._blueprints[tenant_name]


def _streamed_audit_log(data):
    line = data.strip().decode(errors='ignore')
    if line:
        yield json.loads(line)

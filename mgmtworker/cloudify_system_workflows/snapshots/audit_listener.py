import asyncio
import json
from datetime import datetime
from queue import Queue
from threading import Event, Thread

from cloudify.exceptions import NonRecoverableError
from cloudify_async_client.audit_log import AuditLogAsyncClient


class AuditLogListener(Thread):
    """AuditLogListener is a threaded wrapper for AuditLogAsyncClient.stream"""
    def __init__(self, client: AuditLogAsyncClient, queue: Queue, **kwargs):
        if not hasattr(client, 'stream'):
            raise NonRecoverableError('Asynchronous client for audit_log has '
                                      'not been initialised.')
        super().__init__(daemon=kwargs.pop('daemon', True), **kwargs)
        self._client = client
        self._queue = queue
        self._loop = asyncio.new_event_loop()
        self.stopped = Event()

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
                response = await self._client.stream(since=since)
                async for data in response.content:
                    for audit_log in _streamed_audit_log(data):
                        self._queue.put(audit_log)
                        since = audit_log.get('created_at')
            except Exception:
                pass


def _streamed_audit_log(data):
    line = data.strip().decode(errors='ignore')
    if line:
        yield json.loads(line)

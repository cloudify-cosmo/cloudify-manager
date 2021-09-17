import asyncio
import logging
import json

import asyncpg


class ListenerException(Exception):
    pass


class TaskAlreadyExists(ListenerException):
    def __init__(self, channel: str):
        self.channel = channel


class TaskNotDefined(ListenerException):
    def __init__(self, channel: str):
        self.channel = channel


class Listener:
    def __init__(self, dsn: str, logger: logging.Logger):
        self.dsn = dsn
        self.logger = logger
        self.conn_listen = None
        self.loop = asyncio.get_event_loop()
        self.channels = {}

    def listen_on_channel(self, channel: str):
        if channel in self.channels.keys():
            raise TaskAlreadyExists(channel)
        self.channels[channel] = {
            'task': self.loop.create_task(self._listener(channel)),
            'queues': set(),
        }
        self.logger.debug("Started listening for notification on %s", channel)

    def attach_queue(self, channel: str, queue: asyncio.Queue):
        if channel not in self.channels.keys():
            raise TaskNotDefined(channel)
        self.channels[channel]['queues'].add(queue)

    def remove_queue(self, channel: str, queue: asyncio.Queue):
        if channel not in self.channels.keys():
            raise TaskNotDefined(channel)
        try:
            self.channels[channel]['queues'].remove(queue)
            self.logger.debug("Queue %s removed from channel %s.",
                              queue, channel)
        except KeyError:
            self.logger.info("Queue removal unnecessary: %s has been already "
                             "removed from channel %s.", queue, channel)

    async def _listener(self, channel: str):
        if not self.conn_listen:
            self.conn_listen = await asyncpg.connect(self.dsn)

        await self.conn_listen.add_listener(
            channel,
            lambda *args: self.loop.create_task(self._process(*args)))

    async def _process(self,
                       conn: asyncpg.connection.Connection,
                       pid: int,
                       channel: str,
                       data: str):
        record = json.loads(data)
        if channel in self.channels.keys():
            for q in self.channels[channel].get('queues', []):
                q.put_nowait(record)

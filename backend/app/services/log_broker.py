import asyncio
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Iterable

from fastapi import WebSocket

from ..schemas import LogEntry, ServiceName


class LogBroker:
    def __init__(self, max_entries: int = 5000):
        self._logs: deque[LogEntry] = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._clients: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(
        self,
        service: ServiceName,
        stream: str,
        message: str,
        source: str = "system",
    ) -> None:
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            service=service,
            stream=stream,  # type: ignore[arg-type]
            source=source,  # type: ignore[arg-type]
            message=message.rstrip(),
        )
        with self._lock:
            self._logs.append(entry)

        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(self._broadcast(entry), self._loop)

    def history(self, service: ServiceName | None = None, limit: int = 200) -> list[LogEntry]:
        with self._lock:
            data = list(self._logs)
        if service:
            data = [item for item in data if item.service == service]
        return data[-limit:]

    async def register(self, websocket: WebSocket, backlog: Iterable[LogEntry]) -> None:
        await websocket.accept()
        self._clients.add(websocket)
        for entry in backlog:
            await websocket.send_json(entry.model_dump(mode="json"))

    async def unregister(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)
        try:
            await websocket.close()
        except Exception:
            pass

    async def _broadcast(self, entry: LogEntry) -> None:
        dead: list[WebSocket] = []
        payload = entry.model_dump(mode="json")
        for client in list(self._clients):
            try:
                await client.send_json(payload)
            except Exception:
                dead.append(client)
        for client in dead:
            self._clients.discard(client)


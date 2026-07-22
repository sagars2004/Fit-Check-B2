from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class JobEvent:
    job_id: str
    stage: str
    progress: int
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_sse(self) -> str:
        payload = {
            "job_id": self.job_id,
            "stage": self.stage,
            "progress": self.progress,
            "data": self.data,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
        }
        return f"data: {json.dumps(payload)}\n\n"


class EventBroadcaster:
    """In-memory event broadcaster for streaming Server-Sent Events (SSE)."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[JobEvent]]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue[JobEvent]:
        queue: asyncio.Queue[JobEvent] = asyncio.Queue()
        if job_id not in self._subscribers:
            self._subscribers[job_id] = []
        self._subscribers[job_id].append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue[JobEvent]) -> None:
        if job_id in self._subscribers:
            try:
                self._subscribers[job_id].remove(queue)
                if not self._subscribers[job_id]:
                    del self._subscribers[job_id]
            except ValueError:
                pass

    def publish(self, event: JobEvent) -> None:
        subscribers = self._subscribers.get(event.job_id, [])
        for queue in subscribers:
            queue.put_nowait(event)

    async def stream_events(self, job_id: str) -> AsyncGenerator[str, None]:
        queue = self.subscribe(job_id)
        try:
            # Yield initial connected frame
            yield f"data: {json.dumps({'status': 'connected', 'job_id': job_id})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event.to_sse()
                    if event.progress >= 100 or event.stage in ("complete", "failed"):
                        break
                except TimeoutError:
                    # Keep-alive heartbeat comment
                    yield ": keep-alive\n\n"
        finally:
            self.unsubscribe(job_id, queue)


broadcaster = EventBroadcaster()

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List


class LiveEventPublisher:
    def __init__(self) -> None:
        self._subscribers: List[asyncio.Queue] = []
        self._history: deque[Dict[str, Any]] = deque(maxlen=200)

    def subscribe(self) -> asyncio.Queue:
        channel = asyncio.Queue()
        self._subscribers.append(channel)
        return channel

    def publish(self, event_type: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        event = {
            'type': event_type,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'payload': payload or {},
        }
        self._history.append(event)
        for channel in list(self._subscribers):
            channel.put_nowait(event)
        return event

    def snapshot(self, limit: int = 50) -> List[Dict[str, Any]]:
        size = max(1, min(int(limit), len(self._history)))
        return list(self._history)[-size:]

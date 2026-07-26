"""Bus d'événements thread-safe: fan-out vers les clients SSE."""
from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any

_MAX_QUEUE = 2000


class Subscriber:
    __slots__ = ("q", "id", "dropped")

    def __init__(self, sub_id: int) -> None:
        self.q: queue.Queue = queue.Queue(maxsize=_MAX_QUEUE)
        self.id = sub_id
        self.dropped = 0

    def push(self, payload: str) -> None:
        try:
            self.q.put_nowait(payload)
        except queue.Full:
            # Client trop lent: on jette le plus vieux plutôt que de bloquer le serveur.
            self.dropped += 1
            try:
                self.q.get_nowait()
                self.q.put_nowait(payload)
            except (queue.Empty, queue.Full):
                pass

    def get(self, timeout: float):
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[int, Subscriber] = {}
        self._lock = threading.Lock()
        self._next_id = 1

    def subscribe(self) -> Subscriber:
        with self._lock:
            sub = Subscriber(self._next_id)
            self._next_id += 1
            self._subs[sub.id] = sub
            return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        with self._lock:
            self._subs.pop(sub.id, None)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._subs)

    def emit(self, event: str, data: Any) -> None:
        payload = "event: %s\ndata: %s\n\n" % (
            event,
            json.dumps(data, separators=(",", ":"), default=str),
        )
        with self._lock:
            subs = list(self._subs.values())
        for sub in subs:
            sub.push(payload)

    def heartbeat(self) -> None:
        payload = ": ping %d\n\n" % int(time.time())
        with self._lock:
            subs = list(self._subs.values())
        for sub in subs:
            sub.push(payload)


BUS = EventBus()

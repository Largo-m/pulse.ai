from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any


@dataclass
class PromptRequest:
    id: str
    kind: str
    payload: dict[str, Any]
    event: threading.Event = field(default_factory=threading.Event)
    answer: Any = None
    cancelled: bool = False


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[Queue[dict[str, Any] | None]] = []
        self._history: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._closed = False

    def publish(self, event: dict[str, Any]) -> None:
        with self._lock:
            if self._closed:
                return
            self._history.append(event)
            dead: list[Queue[dict[str, Any] | None]] = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except Exception:
                    dead.append(queue)
            for queue in dead:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

    def subscribe(self, *, after: int = 0) -> Iterator[dict[str, Any]]:
        queue: Queue[dict[str, Any] | None] = Queue()
        with self._lock:
            for event in self._history[after:]:
                queue.put_nowait(event)
            self._subscribers.append(queue)
        try:
            while True:
                item = queue.get()
                if item is None:
                    break
                yield item
        finally:
            with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            for queue in self._subscribers:
                queue.put_nowait(None)


class PromptCorrelator:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._pending: dict[str, PromptRequest] = {}
        self._lock = threading.Lock()

    def request(self, kind: str, payload: dict[str, Any], *, timeout: float = 3600.0) -> Any:
        prompt_id = str(uuid.uuid4())
        req = PromptRequest(id=prompt_id, kind=kind, payload=payload)
        with self._lock:
            self._pending[prompt_id] = req
        self._bus.publish(
            {
                "type": "prompt.request",
                "id": prompt_id,
                "kind": kind,
                "payload": payload,
            }
        )
        finished = req.event.wait(timeout=timeout)
        with self._lock:
            self._pending.pop(prompt_id, None)
        if not finished or req.cancelled:
            return None
        return req.answer

    def answer(self, prompt_id: str, answer: Any) -> bool:
        with self._lock:
            req = self._pending.get(prompt_id)
            if req is None:
                return False
            req.answer = answer
            req.event.set()
        self._bus.publish({"type": "prompt.answered", "id": prompt_id})
        return True

    def cancel(self, prompt_id: str) -> bool:
        with self._lock:
            req = self._pending.get(prompt_id)
            if req is None:
                return False
            req.cancelled = True
            req.event.set()
        return True

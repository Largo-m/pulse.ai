from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any

from pulse.daemon.protocol import PING, REPLAY_END


@dataclass
class PromptRequest:
    id: str
    kind: str
    payload: dict[str, Any]
    event: threading.Event = field(default_factory=threading.Event)
    answer: Any = None
    cancelled: bool = False
    created_at: float = field(default_factory=time.time)


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

    def subscribe(self, *, after: int = 0, poll: float = 5.0) -> Iterator[dict[str, Any]]:
        """The run's past events, then live ones, in one sequence.

        `stream.replay_end` marks where the past ends, so a late attacher does not
        reopen an answered question. `stream.ping` is a heartbeat that gives the
        consumer a regular point to drop the stream.
        """
        queue: Queue[dict[str, Any] | None] = Queue()
        with self._lock:
            for event in self._history[after:]:
                queue.put_nowait(event)
            queue.put_nowait({"type": REPLAY_END, "count": len(self._history)})
            self._subscribers.append(queue)
        try:
            while True:
                try:
                    item = queue.get(timeout=poll)
                except Empty:
                    yield {"type": PING}
                    continue
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

    def pending(self) -> list[PromptRequest]:
        """Unanswered prompts; this is what makes Home show the run as awaiting input."""
        with self._lock:
            return list(self._pending.values())

    def pending_since(self) -> float | None:
        """When the wait started: the oldest open prompt.

        The oldest, not the newest, so a later prompt does not reset the wait.
        """
        with self._lock:
            opened = [item.created_at for item in self._pending.values()]
        return min(opened) if opened else None

    def request(self, kind: str, payload: dict[str, Any], *, timeout: float | None = None) -> Any:
        """Ask the client and wait, with no timeout by default.

        Runs keep waiting in the background until someone answers; only an
        explicit stop ends the wait.
        """
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

    def cancel_all(self) -> int:
        """Cancel every open prompt and return how many there were.

        Used when stopping a run: the engine waits without timeout, so otherwise
        the thread would stay blocked in `event.wait()` forever.
        """
        with self._lock:
            open_ids = list(self._pending)
        for prompt_id in open_ids:
            self.cancel(prompt_id)
        return len(open_ids)

    def cancel(self, prompt_id: str) -> bool:
        with self._lock:
            req = self._pending.get(prompt_id)
            if req is None:
                return False
            req.cancelled = True
            req.event.set()
        self._bus.publish({"type": "prompt.answered", "id": prompt_id})
        return True

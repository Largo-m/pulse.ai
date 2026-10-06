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
    #: Quando a pergunta foi aberta, em tempo de parede — é o que permite dizer
    #: "esperando há 7min" numa tela que nasceu depois da pergunta.
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
        """O passado da run e depois o vivo, na mesma sequência.

        `stream.replay_end` separa os dois: quem anexa no meio da run precisa
        saber onde o passado acaba para não reabrir uma pergunta já respondida.
        `stream.ping` é o batimento — dá ao consumidor um ponto de retorno
        regular para largar o stream sem que a run precise emitir nada.
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
        """Perguntas sem resposta. É o que faz a Home dizer "aguardando você"."""
        with self._lock:
            return list(self._pending.values())

    def pending_since(self) -> float | None:
        """Quando a espera começou: a pergunta aberta há mais tempo.

        A mais antiga, e não a mais recente, porque é ela que mede há quanto
        tempo a run está parada — uma segunda pergunta aberta depois não
        rejuvenesce a espera.
        """
        with self._lock:
            opened = [item.created_at for item in self._pending.values()]
        return min(opened) if opened else None

    def request(self, kind: str, payload: dict[str, Any], *, timeout: float | None = None) -> Any:
        """Pergunta ao cliente e espera — sem prazo, por padrão.

        O prazo de uma hora que existia aqui matava a premissa do background: a
        pessoa saía do cockpit, a pergunta expirava sozinha e o agente recebia
        "cancelado" sem ninguém ter decidido nada. Sem ninguém para responder, a
        run espera; quem encerra isso é `parar`, que é uma decisão.
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
        """Cancela toda pergunta aberta e devolve quantas eram.

        Existe para a parada da run: o motor espera a resposta sem prazo, então
        uma run parada enquanto perguntava algo ficaria com a thread presa em
        `event.wait()` para sempre — o pedido de parada chegava, e nada nele
        acordava quem estava bloqueado na pergunta.
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
        # Mesmo evento de quem respondeu: para o replay o que importa é que o id
        # morreu, não como. Sem isto, anexar depois reabria a pergunta cancelada.
        self._bus.publish({"type": "prompt.answered", "id": prompt_id})
        return True

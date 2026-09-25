"""Pausar, retomar e parar uma run em andamento.

O workflow roda numa thread do daemon e conversa com o agente por uma sessão
ACP isolada por step (fase ou task). Não dá para congelar um turno do agente no
meio: ou ele termina, ou é descartado. Então o contrato aqui é:

* **pausar** corta o turno em voo (`session/cancel`) e segura o fluxo na
  barreira. O step interrompido volta para pendente — ao retomar ele é refeito
  do começo. Step já concluído e salvo nunca é refeito.
* **parar** corta do mesmo jeito, mas encerra a run. O que já foi salvo continua
  no `workflow.yaml`, então dá para retomar ou refazer depois pelo histórico.

`RunControl` é compartilhado entre a thread da run e quem manda os comandos
(daemon/API), por isso todo estado passa pelo lock.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

#: Código de saída de uma run parada pelo usuário. Não é falha: o cockpit
#: oferece retomar em vez de mostrar erro.
RUN_STOPPED = 130

PAUSED = "paused"
RESUMED = "resumed"
STOPPED = "stopped"


class RunControl:
    """Estado de pausa/parada de uma run, seguro entre threads."""

    def __init__(self, on_change: Callable[[str], None] | None = None) -> None:
        self._lock = threading.Lock()
        #: Desligado enquanto pausado; quem espera na barreira acorda quando liga.
        self._running = threading.Event()
        self._running.set()
        self._paused = False
        self._stopped = False
        self._on_change = on_change

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def stopped(self) -> bool:
        return self._stopped

    @property
    def interrupted(self) -> bool:
        """Há um corte pedido — o turno em voo deve ser cancelado."""
        return self._paused or self._stopped

    def pause(self) -> bool:
        with self._lock:
            if self._stopped or self._paused:
                return False
            self._paused = True
            self._running.clear()
        self._emit(PAUSED)
        return True

    def resume(self) -> bool:
        with self._lock:
            if self._stopped or not self._paused:
                return False
            self._paused = False
            self._running.set()
        self._emit(RESUMED)
        return True

    def stop(self) -> bool:
        with self._lock:
            if self._stopped:
                return False
            self._stopped = True
            self._paused = False
            # Solta quem estiver na barreira para a run poder encerrar.
            self._running.set()
        self._emit(STOPPED)
        return True

    def wait_while_paused(self) -> bool:
        """Segura aqui enquanto pausado. Devolve `False` se a run foi parada."""
        while True:
            if self._stopped:
                return False
            if not self._paused:
                return True
            self._running.wait(0.2)

    def checkpoint(self) -> bool:
        """Ponto de corte entre steps. `False` quando a run não deve seguir."""
        return self.wait_while_paused()

    def _emit(self, kind: str) -> None:
        if self._on_change is None:
            return
        try:
            self._on_change(kind)
        except Exception:
            # Notificar é acessório: nunca pode derrubar quem pausou.
            pass

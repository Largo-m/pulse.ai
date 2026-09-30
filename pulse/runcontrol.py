"""Parar uma run em andamento — e o contrato de retomar depois.

O workflow roda numa thread do daemon e conversa com o agente por uma sessão
ACP isolada por step. Não dá para congelar um turno do agente no meio: ou ele
termina, ou é descartado. Por isso existe um comando só:

* **parar** corta o turno em voo (`session/cancel`) e encerra a run inteira com
  `RUN_STOPPED`. O step que estava em execução volta para pendente — ele não
  terminou, então não conta como feito nem como falha.
* **retomar** não é um estado desta classe: é começar uma run nova sobre o mesmo
  registro (`resume_run_id`). O que já foi salvo continua em `run_steps`, então o
  fluxo recomeça do primeiro step que não fechou, sem refazer o que já fechou.

Não há pausa: segurar a run viva esperando o usuário custava uma thread e uma
sessão ACP abertas por tempo indefinido, e entregava o mesmo resultado que parar
e retomar — o step cortado é refeito do começo nos dois casos.

`RunControl` é compartilhado entre a thread da run e quem manda o comando
(daemon/API), por isso todo estado passa pelo lock.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

#: Código de saída de uma run parada pelo usuário. Não é falha: o cockpit
#: oferece retomar em vez de mostrar erro.
RUN_STOPPED = 130

STOPPED = "stopped"


class RunControl:
    """Estado de parada de uma run, seguro entre threads."""

    def __init__(self, on_change: Callable[[str], None] | None = None) -> None:
        self._lock = threading.Lock()
        self._stopped = False
        self._on_change = on_change

    @property
    def stopped(self) -> bool:
        return self._stopped

    @property
    def interrupted(self) -> bool:
        """Há um corte pedido — o turno em voo deve ser cancelado."""
        return self._stopped

    def stop(self) -> bool:
        with self._lock:
            if self._stopped:
                return False
            self._stopped = True
        self._emit(STOPPED)
        return True

    def checkpoint(self) -> bool:
        """Ponto de corte entre steps. `False` quando a run não deve seguir."""
        return not self._stopped

    def _emit(self, kind: str) -> None:
        if self._on_change is None:
            return
        try:
            self._on_change(kind)
        except Exception:
            # Notificar é acessório: nunca pode derrubar quem parou.
            pass

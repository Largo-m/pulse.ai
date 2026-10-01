from __future__ import annotations

#: 4 — `run.context`: onde a run trabalha (o worktree, quando há um) e em que
#: branch. Daemon mais velho roda sempre na raiz do projeto e não emite o
#: evento, então a tela mostraria artefato no lugar errado e branch nenhuma.
#:
#: 3 — anexar a uma run viva: `GET /api/runs`, `?after` no SSE, e os marcadores
#: `stream.replay_end`/`stream.ping`. Daemon mais velho não sabe reabrir uma run,
#: então o cliente o substitui em vez de conversar com ele.
ENGINE_PROTOCOL = 4

#: Fim do passado reenviado, começo do vivo. Um cliente que anexa a uma run em
#: curso recebe o histórico dela primeiro; é este marcador que diz onde ele
#: acaba, para não reabrir pergunta já respondida.
REPLAY_END = "stream.replay_end"
#: Batimento do stream ocioso. Não é dado da run: serve para o cliente ter um
#: ponto de retorno regular mesmo quando a run não emite nada.
PING = "stream.ping"

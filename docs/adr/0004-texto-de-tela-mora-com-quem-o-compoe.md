# ADR 0004 — O texto de tela mora com a camada que o compõe

## Status

Aceito

## Data

2026-10-08

## Decisores

Jonathan Matos

## Contexto e problema

O Pulse fala português com o usuário e inglês no código. A maior parte do
texto de tela vive na TUI (`pulse/tui/strings.py`), mas o motor, os construtores
de resposta, o log da run e o cliente também compõem frases que alguém lê na
tela: avisos da run, o menu de step bloqueado, rótulos de diálogo, palavras de
status.

Esse texto estava em `pulse/domain/ui_text.py`, e a justificativa era o próprio
problema: o domínio é o único pacote que **todas** as camadas podem importar.
Era um contorno da regra de camadas, não um lugar — o domínio virou o ponto de
encontro de cópia de UI, e dois textos cruzavam camadas por *parsing* de
string:

- `acp/` emitia `"Modelo: X"` como título de um `session_info_update` falso, e a
  TUI lia o nome do modelo de volta com uma regex;
- `acp/` montava `"Plan — continuação (2)"` como título de fase, e a TUI tirava
  o sufixo com outra regex para achar o step.

Mudar a palavra no produtor quebrava o leitor em silêncio.

## Fatores de decisão

- AGENTS.md §2.1: o domínio não depende de UI; o que dois lados compartilham
  mora com o dono ou no contrato do fio, não num pacote "que todos importam".
- Dado que cruza camadas viaja como dado, não como texto montado (§3, "parse at
  the boundary").
- Não reescrever o que o motor narra: os avisos dele são saída do motor e
  continuam sendo compostos por ele.
- O histórico já gravado (`run_events`) precisa reabrir igual.

## Opções consideradas

1. **Mover `ui_text.py` para um pacote folha `pulse/copy/`**, com contrato
   "não importa nada". Só troca o nome do contorno: continua um ponto central
   que toda camada importa.
2. **Códigos de mensagem + renderização na tela** (i18n). O motor emitiria
   `{"code": "run_stopped_at", "label": …}` e cada cliente traduziria. Resolve
   tudo, mas muda o `StreamSink`, o `PromptPort` (menus por rótulo), o SSE, o
   console e o formato de `run_events` gravado — e não há segunda língua no
   horizonte.
3. **Cada texto com o dono que o compõe; o que cruza camada vira campo.**

## Decisão

Opção 3.

| Texto | Dono | Lido por |
|---|---|---|
| Avisos da run, menu de step, motivo de não concluir | [`orchestrator/wording.py`](../../pulse/orchestrator/wording.py) | só o motor |
| Opções injetadas, rótulos de permissão, fallbacks | [`replies/wording.py`](../../pulse/replies/wording.py) | `replies/`, `history/`, `tui/` |
| Bolhas do diálogo, respostas gravadas, marcador de continuação | [`history/log_wording.py`](../../pulse/history/log_wording.py) | `history/`, `tui/` |
| Palavras de status | [`history/status_labels.py`](../../pulse/history/status_labels.py) | quem desenha status |
| Linha de uma run viva (`loop · step · há 3min`) | [`history/run_lines.py`](../../pulse/history/run_lines.py) | Home e `pulse daemon status` |
| Títulos de erro que a sessão cliente acrescenta | [`client/run_session.py`](../../pulse/client/run_session.py) | `tui/strings.py` |

Os dois textos que cruzavam camadas viraram campos do contrato:

- `StreamSink.set_model(model)` e o evento SSE `session.model`;
- `StreamSink.begin_phase(title, turn=n)` e o campo `turn` de `phase.begin`. O
  log gravado continua com o marcador `"— continuação (n)"`, agora composto por
  `history/log_wording.py`, então runs antigas e novas reabrem iguais.

`ENGINE_PROTOCOL` sobe para 7: um daemon antigo mandaria o título montado.

**Diagnóstico não é cópia de tela.** As mensagens dos checks de runtime
(`RuntimeCheck.message`), do doctor e do teste de conexão ACP são compostas
pelos adaptadores e servem a dois leitores: `pulse doctor` no terminal e as telas
de onboarding e configurações. Ficam em inglês, como erro e log (AGENTS.md
§4.1). A tela dá o contexto em português — o cabeçalho (`Ambiente — Cursor`,
`Conexão ACP`) e a decisão a partir do `status` — e mostra a mensagem como o
detalhe técnico, sem traduzir. Traduzi-las pediria códigos de mensagem com
parâmetros no contrato `/api/*`, que é a opção 2 acima.

## Consequências

- Boas: nenhum módulo de texto é importado por todas as camadas; mudar uma
  palavra não quebra um leitor em outra camada; o domínio volta a ter só
  valores e portas.
- Ruins: o texto em português fica em quatro lugares em vez de um; revisar a
  voz do produto exige olhar a tabela acima.
- Fitness functions: três contratos `protected` do import-linter fixam quem
  importa cada módulo de texto, e
  `test_the_domain_holds_no_screen_copy_module` impede que o domínio volte a
  ter um.
- Se o Pulse um dia falar outra língua, a opção 2 continua aberta: os pontos de
  composição já estão separados por dono.

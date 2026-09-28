# Questions

O Pulse **não deixa o agente perguntar em arquivo**. A skill proíbe `.pulse/skills/.../questions` e qualquer rascunho de pergunta. O único canal é o terminal / TUI.

Há **dois jeitos** de o agente perguntar, mais um irmão (permissão). Os três caem no mesmo `PromptHandler`.

```
agente
  ├─ texto com ```text          → parse_text_questionnaire
  │                               (depois do turn)
  ├─ JSON-RPC cursor/ask_question → respond_to_ask_question
  │                               (no meio do turn)
  └─ MCP tools/call AskQuestion   → o mesmo handler
        │
        ▼
PromptHandler  (terminal / questionary)
  ou
TextualPromptHandler → PromptBridge → PromptDock (TUI)
        │
        ▼
resposta volta ao agente
  ou
Pulse classifica o outcome (aprovar / ajustar / cancelar / …)
```

## 1. Questionário de texto (o fluxo principal)

A skill `user-input.md` manda o agente **terminar** a resposta com um bloco:

````text
```text
Preciso de algumas informações antes de continuar.
1. Aprovar PRD (.pulse/specs/features/x/PRD.md) e avançar?
A) Sim, aprovar e continuar
B) Não, preciso de ajustes (descreva)
C) Cancelar workflow
```
````

Regras que o parser exige (`pulse/presentation/prompt/text_questionnaire.py`):

- header `Preciso de algumas informações…` ou `I need some information…`
- pergunta `N. texto`
- opções `A) texto` (uma por linha)
- de preferência dentro de ` ```text `
- `Resposta:` no fim é ignorado (é para o chat, não para o Pulse)

Enquanto o texto chega, `CockpitSink` / `StreamRenderer` entram em **questionnaire mode**: param de imprimir o bloco e mostram só `Questionário interativo`.

Depois do `session/prompt` acabar, o runner chama `_run_text_questionnaire`:

| Parser | Significado |
| --- | --- |
| bloco inválido / ausente | retorna `""` — ninguém perguntou |
| usuário cancela (Esc) | retorna `None` — workflow cancela |
| usuário responde | texto `→ A) Sim, aprovar…` |

O handler mostra **uma pergunta por vez**. Sem opções → campo livre. Opção com “(descreva)” → select + texto. “Outro” → texto livre (`__other__`).

O Pulse **injeta** `Outro (descreva)` sozinho, **exceto** em perguntas fechadas de aprovação / migração / “funciona como esperado”.

## 2. `cursor/ask_question` (durante o turn)

O agent pode mandar um request JSON-RPC no stdout. O `AcpSessionRunner` não trata isso como `session/update`: chama `_handle_agent_request`.

Payload típico:

```json
{
  "title": "Preciso de algumas informações antes de continuar.",
  "questionIndex": 1,
  "totalQuestions": 2,
  "questions": [
    {
      "id": "q1",
      "prompt": "Qual stack?",
      "options": [{"id": "a", "label": "Python"}, {"id": "b", "label": "Go"}],
      "allowMultiple": false
    }
  ]
}
```

Resposta que volta no JSON-RPC:

```json
{
  "outcome": {
    "outcome": "answered",
    "answers": [{"questionId": "q1", "selectedOptionIds": ["a"]}]
  }
}
```

Cancelar: `{"outcome": {"outcome": "cancelled"}}`.

Descrição extra (opção “descreva”) vai no id: `"B::o botão some no mobile"`.

Este canal **não** passa pelo classificador de fase. A resposta vai direto ao agente, que continua o mesmo turn.

## 3. MCP `AskQuestion`

No `start()` do runner sobe um HTTP local (`AskQuestionHttpServer`, `127.0.0.1` porta aleatória, path `/mcp`).

`session/new` registra:

```json
{ "type": "http", "name": "pulse-ask", "url": "http://127.0.0.1:<porta>/mcp" }
```

O agente chama `tools/call` com a tool `AskQuestion` (schema em `pulse/mcp/ask_protocol.py`). O servidor usa o **mesmo** `respond_to_ask_question`. O resultado vira texto JSON no content da tool.

Existe também um bridge Unix socket (`AskQuestionBridgeServer`) para testes / stdio. O caminho de produção do runner é o HTTP.

## 4. Onde a UI aparece

| Superfície | Handler | Widget |
| --- | --- | --- |
| Menu terminal (Rich) | `PromptHandler` | `questionary.select` / `checkbox` / `text` |
| TUI cockpit | `TextualPromptHandler` | `PromptBridge` + `PromptDock` |

Na TUI o worker ACP **bloqueia** num `Future`. A thread da UI faz `poll()` a cada 100 ms, monta o dock no `LogStream` e devolve o resultado. Esc cancela.

Tipos do dock: `select`, `multi_select`, `text`, `confirm`.

## 5. O que o Pulse faz com a resposta

### Fases de planejamento (`new-issue`)

Até **4 turns** (`MAX_PHASE_APPROVAL_TURNS`). Depois de cada turn, classifica a primeira linha `→ …`:

| Outcome | Gatilho (texto) | Efeito |
| --- | --- | --- |
| `approve` | “aprov”, “sim”, `A)` | fase aprovada, segue |
| `cancel` | “cancelar” | para o workflow |
| `skip` | “pular” + “fase” | pula a fase |
| `adjust` | “ajuste” | novo prompt de continuação, sem avançar |
| `continue` | resto | novo prompt, tenta de novo |

Sem bloco de aprovação (`""`): o loop **para sem aprovar**. Se o agente esquecer o ` ```text `, a fase não avança.

### Quick (`fix-bug`)

Até **4 turns** no plano (`MAX_QUICK_PLAN_TURNS`):

| Outcome | Efeito |
| --- | --- |
| `approve` | entra na implementação |
| `cancel` | para |
| `migrate` | não implementa; usuário vai para pipeline completo |
| `reduce_scope` / `adjust` / `continue` | novo prompt de plano |

Sem aprovação, **nenhum código de aplicação** é alterado.

### Setup / analyze

Depois da fase 1, se houver questionário, as respostas entram no prompt da fase 2 (gerar specs). Se não houver bloco, a fase 2 roda mesmo assim (contexto inferido).

### Execute / implement

`run_isolated_prompt` **não** espera questionário de aprovação. Perguntas no meio do turn ainda funcionam via `ask_question` / MCP.

## 6. Irmãos: permissão e plano

Não são “questions” da skill, mas usam o mesmo handler:

- `session/request_permission` / `cursor/request_permission` — política `ask` / `auto_approve` / `deny_writes`
- `cursor/create_plan` — confirm “Aprovar plano?”

`deny_writes` recusa write/edit automaticamente. Shell sem capability de terminal é recusado.

## 7. O que **não** existe mais

No start de todo workflow o Pulse apaga:

- `.pulse/skills/<skill>/questions/`
- `.pulse/handoff/<skill>.md`

Pergunta não é persistida. Só o que sobra é o log do cockpit (`Question` / `Answer`) se a TUI estiver aberta — ver [logs.md](logs.md).

## Design da escolha

**O que:** terminal como único I/O; bloco ` ```text ` como contrato com o agente; MCP/`ask_question` como atalho no meio do turn.

**Por quê:** o agente ACP não tem TUI. O Pulse precisa **parar o processo** e perguntar no mesmo terminal em que o usuário rodou `pulse`. O bloco de texto é parseável sem tool. O MCP cobre o caso em que o modelo prefere chamar `AskQuestion`.

**Alternativas:** arquivos de pergunta no disco, UI web, sempre tool e nunca texto.

**Trade-off:** se o modelo quebrar o formato (`A) B) C)` na mesma linha), o parser ignora o bloco e a fase de planejamento **não aprova**. Por isso a skill é rígida no layout.

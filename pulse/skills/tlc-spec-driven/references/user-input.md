# User Input (CLI)

**Applies to:** Every phase of this skill. All reference docs defer here when user input is required.

## Rules (mandatory)

1. **No intermediate artifacts for questions** — Never create question files, screens, menus, UI components, JSON, Markdown drafts, or any other mechanism to collect answers. The terminal (chat) is the only interaction channel.
2. **Work first, ask last** — Continue executing until it is impossible to proceed without a user decision. Do as much autonomous work as allowed (codebase analysis, drafting, validation) before stopping.
3. **Batch pending questions** — When blocked, present **all** pending questions together at the **end** of the response.
4. **Stop after questions** — End the response immediately after the questions. Do not continue the workflow, create deliverables that depend on answers, or add closing commentary.
5. **Never invent mandatory answers** — Do not assume defaults or fabricate values when information is required. Infer only from explicit user input or verifiable project artifacts (code, `.specs/`, docs).
6. **Resume from interruption** — After the user replies (e.g. `A`, `B`, `1`, `Sim`, or free text), continue exactly from where execution stopped.

## Format

Use plain text suitable for a terminal. Always end with `Resposta:` on its own line.

**Delivery:** Wrap the **entire** question block in a ` ```text ` fenced code block so chat does not collapse line breaks. No markdown lists, bullets, or tables inside the block.

**English equivalent header:** `I need some information before continuing.`

### Pre-send checklist (mandatory)

Before sending, verify ALL of these. If any fails, rewrite — do not send.

| Check | Pass condition |
| ----- | -------------- |
| Numbered questions | Every question line starts with `N.` |
| Options separated | No single line contains `A)` and `B)` (or any two option letters) |
| One option per line | Count of lines matching `^[A-Z]\)` equals total options |
| Blank lines | Empty line after question text; empty line between question blocks |
| Footer | `Resposta:` alone on the last line inside the fence |
| Fence | Whole block inside ` ```text ` … ` ``` ` |

**Detection regex (mental check):** if you see ` B)` or ` C)` or ` D)` anywhere except at the start of a line (after newline), the output is **invalid**.

### Layout rules (strict — violations break readability)

Every CLI question block MUST follow this structure exactly:

1. **Header** — one line, then blank line
2. **Each question** — numbered (`1.`, `2.`, …), question text on its own line, blank line, then options
3. **Each option** — exactly one option per line, format `A) texto` (letter + `)` + space + text)
4. **Between questions** — blank line after the last option of the previous question
5. **Footer** — blank line, then `Resposta:` alone on the last line

**NEVER:**

- Put multiple options on the same line
- Omit question numbers
- Put option text on the same line as the question (without a blank line before options)
- Use markdown lists (`-`, `*`), bullets, tables, or headings inside the question block
- Wrap options in parentheses blocks on one line

**BAD (do not output like this — options collapsed on one line):**

```text
Preciso de algumas informações antes de continuar.

O que você está construindo?
A) Opção A B) Opção B C) Opção C D) Outro

Quem é o público-alvo?
A) Iniciantes B) Experts C) Outro

Resposta:
```

**GOOD (always output like this — inside ```text fence):**

```text
Preciso de algumas informações antes de continuar.

1. O que você está construindo?

A) Plataforma de paper trading
B) Sistema de gestão de portfólio
C) API de negociação
D) Plataforma completa
E) Outro (descreva)

2. Quem é o público-alvo?

A) Investidores iniciantes
B) Traders experientes
C) Ambos
D) Outro (descreva)

Resposta:
```

### Full multi-question example (project-init — use this structure)

```text
Preciso de algumas informações antes de continuar.

1. O que você está construindo?

A) Plataforma de simulação de trading (paper trading)
B) Sistema de gestão de portfólio pessoal com saldo virtual
C) Projeto full-stack de estudo/portfólio
D) Plataforma completa pronta para produção
E) Outro (descreva)

2. Quem é o público-alvo e qual problema resolve?

A) Investidores iniciantes aprendendo a operar
B) Desenvolvedores estudando arquitetura
C) Uso pessoal para simular investimentos
D) Público geral — trading sem risco
E) Outro (descreva)

3. Qual é o foco da v1 neste momento?

A) Consolidar o que existe — gaps, testes, estabilidade
B) Completar features pendentes
C) Preparar para deploy
D) Adicionar novas features (descreva)
E) Outro (descreva escopo e exclusões)

4. Há restrições críticas?

A) Sem prazo — evolução contínua local
B) Prazo curto (descreva)
C) Apenas ambiente local
D) Preparar para produção em breve
E) Outro (descreva)

Resposta:
```

Keep option text short (one line each). If an option needs a sub-prompt (e.g. "descreva"), put it in parentheses at the end of that option line — never merge options to save space.

## Question design

- Options must be **concrete** (`Card layout` not `Option A` as label text — use letters only as selectors).
- Prefer **3–6 options** plus an **Other (describe)** escape when the set is not exhaustive.
- Use **free-text questions** (no alternatives) when the answer is open-ended.
- Group related decisions into one numbered question when possible; do not split into multiple round-trips unless answers depend on each other.
- For yes/no decisions, use `A) Sim` / `B) Não` or `1) Yes` / `2) No`.
- For multi-select, state it explicitly: `(escolha uma ou mais: A, C)`.

## What is NOT a question artifact

These are **deliverables**, not question mechanisms — still create them after answers are received:

- `.specs/project/PROJECT.md`, `ROADMAP.md`, `STATE.md`
- `.specs/features/[feature]/spec.md`, `context.md`, `design.md`, `tasks.md`
- `.specs/codebase/*` brownfield docs
- Validation reports, fix plans, task summaries

`context.md` stores **decisions already made** — never use it (or any file) as a questionnaire or pending-questions log.

## Approval and confirmation

When a phase requires user approval (design, tasks, quick-task pre-check, fix plans), present the deliverable summary first, then blocking questions in CLI format:

```
Preciso de algumas informações antes de continuar.

1. Aprovar [artefato] e prosseguir?

A) Sim, aprovar e continuar
B) Não, preciso de ajustes (descreva abaixo)

Resposta:
```

If the user chooses adjustments, wait for their description before revising.

## UAT and verification

Interactive UAT follows the same strict layout — one option per line, numbered question, blank lines between sections:

```
Preciso de algumas informações antes de continuar.

1. Teste: [Nome do teste]

Esperado: [comportamento observável]

A) Funciona como esperado
B) Não funciona (descreva o que vê)
C) Pular / não aplicável

Resposta:
```

Infer severity from free-text descriptions per [validate.md](validate.md). Never ask the user to rate severity.

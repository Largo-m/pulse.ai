---
name: codebase-explore
description: Mapeia um repositório existente
runtime: cursor
model: gpt-5.5
permission_policy: deny_writes
---

# brownfield-mapping.md

# Brownfield Mapping

**Trigger:** "Map codebase", "Analyze existing code", "Document current architecture"

**Purpose:** Understand existing project structure before adding features.

## Process

Before starting, check if the `codenavi` skill is available for code exploration (see Skill Integrations in SKILL.md). If available, prefer it for all discovery and navigation tasks below.

**High-level approach:**

1. Explore directory structure systematically
2. Identify technology stack from dependency manifests
3. Extract patterns from representative code samples
4. Document observed conventions and architectures
5. Catalog external integrations
6. Identify concerns: tech debt, known bugs, security risks, performance bottlenecks, fragile areas

**Analysis depth:**

- Sample 5-10 representative files per category
- Focus on consistency and patterns, not exhaustive coverage
- Extract actual examples, not assumptions

## Output: 7 Files in .pulse/specs/codebase/

---

### 1. STACK.md

**Purpose:** Document technology stack and dependencies.

**Size limit:** 2,000 tokens (~1,200 words)

**Extract from:**

- Dependency manifest files
- Build configuration
- Runtime configuration

**Document:**

```markdown
# Tech Stack

**Analyzed:** [date]

## Core

- Framework: [detected name + version]
- Language: [detected name + version]
- Runtime: [detected name + version]
- Package manager: [detected manager]

## Frontend (if applicable)

- UI Framework: [name + version]
- Styling: [approach + tools]
- State Management: [library/pattern]
- Form Handling: [library if present]

## Backend (if applicable)

- API Style: [REST/GraphQL/gRPC + framework]
- Database: [ORM/query builder + database system]
- Authentication: [library/approach]

## Testing

- Unit: [framework]
- Integration: [framework]
- E2E: [framework if present]

## External Services

- [Category]: [Service name]
- [Category]: [Service name]

## Development Tools

- [Tool category]: [Tool name]
```

**Instructions:**

- Extract from actual dependency files
- Include versions for major dependencies
- Categorize by purpose
- Note testing frameworks explicitly

---

### 2. ARCHITECTURE.md

**Purpose:** Document architectural patterns and data flow.

**Size limit:** 4,000 tokens (~2,400 words)

**Extract from:**

- Directory organization
- Code structure analysis
- Repeated patterns across files

**Document:**

```markdown
# Architecture

**Pattern:** [Identified pattern - monolith/microservices/modular/etc]

## High-Level Structure

[Create diagram/description based on actual organization]

## Identified Patterns

### [Pattern Name]

**Location:** [where this pattern lives]
**Purpose:** [what this achieves]
**Implementation:** [how it's structured]
**Example:** [reference to actual file/function]

### [Pattern Name]

[Same structure]

## Data Flow

### [Key Flow - e.g., Authentication/Payment/etc]

[Map actual flow from code analysis]

### [Key Flow]

[Map actual flow]

## Code Organization

**Approach:** [feature-based/layer-based/domain-driven/etc]

**Structure:**
[Document actual directory organization]

**Module boundaries:**
[How code is divided into modules/packages]
```

**Instructions:**

- Identify patterns from actual code, not assumptions
- Document observed architectural decisions
- Create flow diagrams for critical paths
- Reference concrete examples from codebase

---

### 3. CONVENTIONS.md

**Purpose:** Document code style and naming conventions.

**Size limit:** 3,000 tokens (~1,800 words)

**Extract from:**

- Analyzing 5-10 representative files
- Identifying consistent patterns
- Observing actual conventions in use

**Document:**

```markdown
# Code Conventions

## Naming Conventions

**Files:**
[Observed pattern - document actual approach]
Examples: [actual filenames from codebase]

**Functions/Methods:**
[Observed pattern]
Examples: [actual function names]

**Variables:**
[Observed pattern]
Examples: [actual variable names]

**Constants:**
[Observed pattern]
Examples: [actual constant names]

## Code Organization

**Import/Dependency Declaration:**
[Observed ordering pattern]
[Example from actual file]

**File Structure:**
[Observed organization within files]
[Example from actual file]

## Type Safety/Documentation

**Approach:** [Type system/documentation approach used]
[Example from actual code]

## Error Handling

**Pattern:** [Observed error handling approach]
[Example from actual code]

## Comments/Documentation

**Style:** [When/how comments are used]
[Example from actual code]
```

**Instructions:**

- Extract patterns from actual code samples
- Document observed conventions, not ideal conventions
- Include concrete examples from codebase
- Note exceptions or variations where found

---

### 4. STRUCTURE.md

**Purpose:** Document directory layout and file organization.

**Size limit:** 2,000 tokens (~1,200 words)

**Document:**

```markdown
# Project Structure

**Root:** [project root path]

## Directory Tree

[Visual tree representation - max 3 levels deep]

## Module Organization

### [Module/Area Name]

**Purpose:** [what this area handles]
**Location:** [where files live]
**Key files:** [important files in this area]

### [Module/Area Name]

[Same structure]

## Where Things Live

**[Capability/Feature]:**

- UI/Interface: [location]
- Business Logic: [location]
- Data Access: [location]
- Configuration: [location]

**[Capability/Feature]:**
[Same structure]

## Special Directories

**[Directory name]:**
**Purpose:** [what belongs here]
**Examples:** [key files in this directory]
```

**Instructions:**

- Create tree view of actual directory structure
- Limit depth to maintain readability
- Document purpose of key directories
- Map capabilities to physical locations

---

### 5. TESTING.md

**Purpose:** Document testing infrastructure and patterns.

**Size limit:** 4,000 tokens (~2,400 words)

**Document:**

```markdown
# Testing Infrastructure

## Test Frameworks

**Unit/Integration:** [framework name + version]
**E2E:** [framework name + version]
**Coverage:** [tool if used]

## Test Organization

**Location:** [where tests live]
**Naming:** [test file naming pattern]
**Structure:** [how tests are organized]

## Testing Patterns

### Unit Tests

**Approach:** [observed pattern]
**Location:** [where unit tests live]
[Description of actual pattern used]

### Integration Tests

**Approach:** [observed pattern]
**Location:** [where integration tests live]
[Description of actual pattern used]

### E2E Tests

**Approach:** [observed pattern if present]
**Location:** [where E2E tests live]
[Description of actual pattern used]

## Test Execution

**Commands:** [how to run tests]
**Configuration:** [test configuration approach]

## Coverage Targets

**Current:** [if measurable]
**Goals:** [if documented]
**Enforcement:** [if automated]

## Test Coverage Matrix

Analyze the codebase to determine which code layers require which test types.
For each layer, document the required test type, file location pattern, and run command.

| Code Layer | Required Test Type          | Location Pattern       | Run Command |
| ---------- | --------------------------- | ---------------------- | ----------- |
| [layer]    | [unit/integration/e2e/none] | [glob or path pattern] | [command]   |

## Parallelism Assessment

| Test Type | Parallel-Safe? | Isolation Model | Evidence                      |
| --------- | -------------- | --------------- | ----------------------------- |
| [type]    | [Yes/No]       | [description]   | [file/pattern that proves it] |

## Gate Check Commands

| Gate Level | When to Use                            | Command                     |
| ---------- | -------------------------------------- | --------------------------- |
| Quick      | After tasks with unit tests only       | [unit test command]         |
| Full       | After tasks with e2e/integration tests | [unit + e2e commands]       |
| Build      | After phase completion                 | [build + lint + unit + e2e] |
```

**Instructions:**

- Identify test frameworks from dependencies and code
- Document actual testing patterns observed
- Note test organization approach
- Include execution instructions
- **Test Coverage Matrix:** Sample 5-10 existing test files to identify which layers are tested and how. Look at test file locations relative to source to determine patterns. Extract run commands from `package.json`, `project.json`, `Makefile`, CI config. Mark layers with no existing tests as "none" with a note in CONCERNS.md.
- **Parallelism Assessment:** NOT parallel-safe signals: shared DB connection (same URL from config), table-level cleanup in `beforeEach`/`afterAll` (`.del()`, `DELETE FROM`, `TRUNCATE`), shared mock state reset on globals. Parallel-safe signals: per-test DB creation (Testcontainers, dynamic schema, SQLite in-memory), data namespacing (all data keyed by unique test ID), no shared mutable state between test files, all deps mocked (`jest.fn()`, `vi.fn()`).
- **Gate Check Commands:** Extract from actual project commands — do not invent commands.

---

### 6. INTEGRATIONS.md

**Purpose:** Document external service integrations.

**Size limit:** 5,000 tokens (~3,000 words)

**Document:**

```markdown
# External Integrations

## [Service Category]

**Service:** [service name]
**Purpose:** [what this integration provides]
**Implementation:** [where integration lives in code]
**Configuration:** [how service is configured]
**Authentication:** [auth approach if applicable]

## [Service Category]

[Same structure]

## API Integrations

### [API Name]

**Purpose:** [what this API provides]
**Location:** [where API client/code lives]
**Authentication:** [auth method]
**Key endpoints:** [major endpoints used]

## Webhooks

### [Webhook Source]

**Purpose:** [what events are handled]
**Location:** [webhook handler location]
**Events:** [event types processed]

## Background Jobs

**Queue system:** [system if used]
**Location:** [where job definitions live]
**Jobs:** [key background jobs]
```

**Instructions:**

- Identify integrations from code and configuration
- Document authentication approaches
- Note webhook handlers if present
- Include background job infrastructure

---

### 7. CONCERNS.md

**Purpose:** Surface actionable warnings about the codebase — tech debt, known bugs, security gaps, performance bottlenecks, fragile areas, scaling limits, risky dependencies, missing features, and test coverage gaps.

**Size limit:** 5,000 tokens (~3,000 words)

See [concerns.md](concerns.md) for the full template, guidelines, and examples.

**Instructions:**

- Document only concerns backed by evidence (file paths, measurements, reproduction steps)
- Include fix approaches, not just problems
- Omit sections with no findings
- Prioritize by risk/impact
- Use professional, solution-oriented tone

---

## Total Context Budget

**Combined:** ~19,000 tokens (10% of context window)
**Acceptable for:** Brownfield projects requiring codebase understanding
**Loading strategy:** Load relevant docs on-demand based on task

# concerns.md

# Phase: Codebase Concerns

**Trigger:** Part of brownfield mapping, or explicitly "document concerns", "find tech debt", "what's risky in this codebase"

**Purpose:** Surface actionable warnings about the codebase. Focused on "what to watch out for when making changes." This is living documentation, not a complaint list.

## When to Generate

CONCERNS.md is generated as part of the brownfield mapping flow (alongside STACK.md, ARCHITECTURE.md, etc.). It can also be created or updated independently when:

- Exploring a new area of the codebase reveals risks
- A bug investigation uncovers systemic issues
- A feature implementation hits unexpected fragility
- A dependency audit reveals risks

## Process

### 1. Gather Evidence

During codebase exploration, look for concrete signals — not opinions. Evidence sources:

- Code patterns that indicate shortcuts (TODO/FIXME/HACK comments, duplicated logic, missing error handling)
- Test coverage gaps (untested critical paths, missing edge cases)
- Dependency manifests (outdated packages, deprecated libraries, security advisories)
- Performance indicators (N+1 queries, missing indexes, synchronous blocking calls)
- Security patterns (client-side-only auth checks, unvalidated inputs, exposed secrets)

### 2. Classify and Document

Each concern must have: **what** the problem is, **where** it lives (file paths), **why** it matters (impact), and **how** to fix it (approach).

### 3. Prioritize by Risk

Focus on concerns that could cause real damage — data loss, security breaches, user-facing failures, scaling walls. Minor style issues and normal TODOs do not belong here.

---

## Template: `.pulse/specs/codebase/CONCERNS.md`

**Size limit:** 5,000 tokens (~3,000 words)

```markdown
# Codebase Concerns

**Analysis Date:** [YYYY-MM-DD]

## Tech Debt

**[Area/Component]:**

- Issue: [What's the shortcut/workaround]
- Files: [Specific file paths with backticks]
- Why: [Why it was done this way]
- Impact: [What breaks or degrades because of it]
- Fix approach: [How to properly address it]

## Known Bugs

**[Bug description]:**

- Symptoms: [What happens]
- Trigger: [How to reproduce]
- Files: [Where the bug lives]
- Workaround: [Temporary mitigation if any]
- Root cause: [If known]
- Blocked by: [If waiting on something]

## Security Considerations

**[Area requiring security care]:**

- Risk: [What could go wrong]
- Files: [Where the risk lives]
- Current mitigation: [What's in place now]
- Recommendations: [What should be added]

## Performance Bottlenecks

**[Slow operation/endpoint]:**

- Problem: [What's slow]
- Files: [Where the bottleneck lives]
- Measurement: [Actual numbers: "500ms p95", "2s load time"]
- Cause: [Why it's slow]
- Improvement path: [How to speed it up]

## Fragile Areas

**[Component/Module]:**

- Files: [Where the fragility lives]
- Why fragile: [What makes it break easily]
- Common failures: [What typically goes wrong]
- Safe modification: [How to change it without breaking]
- Test coverage: [Is it tested? Gaps?]

## Scaling Limits

**[Resource/System]:**

- Current capacity: [Numbers: "100 req/sec", "10k users"]
- Limit: [Where it breaks]
- Symptoms at limit: [What happens]
- Scaling path: [How to increase capacity]

## Dependencies at Risk

**[Package/Service]:**

- Risk: [e.g., "deprecated", "unmaintained", "breaking changes coming"]
- Impact: [What breaks if it fails]
- Migration plan: [Alternative or upgrade path]

## Missing Critical Features

**[Feature gap]:**

- Problem: [What's missing]
- Current workaround: [How users cope]
- Blocks: [What can't be done without it]
- Implementation complexity: [Rough effort estimate]

## Test Coverage Gaps

**[Untested area]:**

- What's not tested: [Specific functionality]
- Risk: [What could break unnoticed]
- Priority: [High/Medium/Low]
- Difficulty to test: [Why it's not tested yet]

---

_Concerns audit: [date]_
_Update as issues are fixed or new ones discovered_
```

**Include only sections that have findings.** Empty sections should be omitted entirely.

---

## What Belongs vs. What Doesn't

**Include:**

- Tech debt with clear impact and fix approach
- Known bugs with reproduction steps
- Security gaps and mitigation recommendations
- Performance bottlenecks with measurements
- Fragile code that breaks easily
- Scaling limits with numbers
- Dependencies that need attention
- Missing features that block workflows
- Test coverage gaps

**Exclude:**

- Opinions without evidence ("code is messy")
- Complaints without solutions ("auth sucks")
- Future feature ideas (that's for product planning)
- Normal TODOs (those live in code comments)
- Architectural decisions that are working fine
- Minor code style issues

---

## Writing Guidelines

- **Always include file paths** — Concerns without locations are not actionable. Use backticks: `src/file.ts`
- Be specific with measurements ("500ms p95" not "slow")
- Include reproduction steps for bugs
- Suggest fix approaches, not just problems
- Focus on actionable items
- Prioritize by risk/impact

**Tone:** Professional, not emotional. Solution-oriented. Risk-focused. Factual.

- ✅ "N+1 query pattern in `app/api/courses/route.ts` — 1.2s p95 with 50+ courses"
- ❌ "Terrible queries, everything is slow"
- ✅ "Fix: add index on `user_id` in `subscriptions` table"
- ❌ "Needs fixing"

---

## How CONCERNS.md Gets Used

- **Feature planning:** Check CONCERNS.md before designing features that touch flagged areas
- **Risk estimation:** Use fragile areas and scaling limits to estimate change risk
- **Onboarding new sessions:** Load CONCERNS.md to give context about what to watch out for
- **Refactoring prioritization:** Use tech debt and test coverage gaps to plan improvement sprints
- **Implementation phase:** Consult before modifying any flagged component

This is living documentation. Update as issues are fixed or new ones discovered during any workflow phase.

# code-analysis.md

# Code Analysis Tools

Use graceful degradation for code search and structural analysis.

## Tool Priority

1. **ast-grep** (`sg`) - Structural pattern-based search
2. **ripgrep** (`rg`) - Fast context-aware text search
3. **grep** - Standard text search (always available)

## Detection

Check tool availability before use:

```bash
# Check for ast-grep
if command -v sg >/dev/null 2>&1; then
  # Use ast-grep for structural search
elif command -v rg >/dev/null 2>&1; then
  # Fall back to ripgrep
else
  # Use standard grep as final fallback
fi
```

## Usage Examples

**Finding function definitions:**

```bash
# ast-grep (best - structural)
sg -p 'function $NAME($$$) { $$$ }'

# ripgrep (fallback - fast text)
rg '^function\s+\w+\(' --type-add 'source:*.[extension]' -t source

# grep (last resort - basic)
grep -r '^function ' --include="*.[extension]"
```

**Finding imports/requires:**

```bash
# ast-grep
sg -p 'import { $$$ } from "$MODULE"'

# ripgrep
rg '^import .* from' --type-add 'source:*.[extension]' -t source

# grep
grep -r '^import ' --include="*.[extension]"
```

**Finding class/component definitions:**

```bash
# ast-grep
sg -p 'class $NAME { $$$ }'

# ripgrep
rg '^(class|export class)\s+\w+' --type-add 'source:*.[extension]' -t source

# grep
grep -r '^class ' --include="*.[extension]"
```

## Search Scope

**Best practices:**

- Limit to source file extensions relevant to project
- Exclude directories: `node_modules`, `vendor`, `dist`, `build`, `.git`
- Focus on source directories: `src`, `lib`, `app`
- Use file type filters when available

**Performance tips:**

- Use specific patterns over broad searches
- Limit directory depth with `--max-depth` (ripgrep/grep)
- Cache results for repeated queries

## Fallback Notice

If ast-grep unavailable, display once per session:

```
⚠️ ast-grep not detected. Install for more precise structural code analysis.
   https://ast-grep.github.io/guide/quick-start.html
```

## When to Use

- Finding usage patterns across codebase
- Identifying code structure and organization
- Locating function/class/component definitions
- Analyzing import/dependency patterns
- Refactoring impact analysis
- Code navigation in unfamiliar codebases

# user-input.md

# User Input (CLI)

**Applies to:** Every phase of this skill. All reference docs defer here when user input is required.

## Rules (mandatory)

1. **No intermediate artifacts for questions** — Never create question files, screens, menus, UI components, JSON, Markdown drafts, or any other mechanism to collect answers. The terminal (chat) is the only interaction channel.
2. **Work first, ask last** — Continue executing until it is impossible to proceed without a user decision. Do as much autonomous work as allowed (codebase analysis, drafting, validation) before stopping.
3. **Batch pending questions** — When blocked, present **all** pending questions together at the **end** of the response.
4. **Stop after questions** — End the response immediately after the questions. Do not continue the workflow, create deliverables that depend on answers, or add closing commentary.
5. **Never invent mandatory answers** — Do not assume defaults or fabricate values when information is required. Infer only from explicit user input or verifiable project artifacts (code, `.pulse/specs/`, docs).
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

- `.pulse/specs/project/PROJECT.md`, `ROADMAP.md`, `STATE.md`
- `.pulse/specs/features/[feature]/spec.md`, `context.md`, `design.md`, `tasks.md`
- `.pulse/specs/quick/NNN-slug/TASK.md`, `SUMMARY.md`
- `.pulse/specs/codebase/*` brownfield docs
- Validation reports, fix plans, task summaries

`context.md` stores **decisions already made** — never use it (or any file) as a questionnaire or pending-questions log.

## Approval and confirmation

When a phase requires user approval (design, tasks, quick-task pre-check, fix plans), create spec deliverables first when applicable (e.g. `.pulse/specs/quick/NNN-slug/TASK.md`), present the summary, then blocking questions in CLI format:

```
Preciso de algumas informações antes de continuar.

1. Aprovar [artefato] e prosseguir?

A) Sim, aprovar e continuar
B) Não, preciso de ajustes (descreva abaixo)

Resposta:
```

If the user chooses adjustments, wait for their description before revising.

## Pipeline migration (Quick mode → full spec)

When a request triggered as Quick mode but fails **Scope Eligibility** in [quick-mode.md](quick-mode.md), present:

```text
Preciso de algumas informações antes de continuar.

1. Este pedido excede o escopo do Quick mode: [motivo concreto — ex.: 5 arquivos, decisão de arquitetura, escopo vago]. Como deseja prosseguir?

A) Migrar para o pipeline completo (Specify → Design → Tasks → Execute, conforme escopo)
B) Quick fix: [recorte pré-definido 1 — uma linha, ≤3 arquivos]
C) Quick fix: [recorte pré-definido 2 — uma linha, ≤3 arquivos]
D) Cancelar

Resposta:
```

- **A)** Start [specify.md](specify.md) for the feature — do not keep a quick TASK.md
- **B/C…)** Re-assess eligibility with that predefined narrowed scope; if it passes, continue Quick mode
- **Last option (Cancelar)** Stop; no spec files unless the user reopens the request

**Closed choices only:** Do not use "descreva" or free-text options in this block. Do not include "Outro" — Pulse suppresses it for migration gates. List concrete quick-fix alternatives derived from your codebase analysis.

**Never** auto-start Specify, Design, or Tasks without the user selecting **A**.

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

# Ambiguity Ledger

Every gray area is **decided** or **N/A** before the phase that owns it closes. Nothing stays silently unclear, and nothing is settled by the agent guessing.

The ledger lives in `PRD.md` as `## Ambiguity Ledger`. Discuss, PRD, Techspec, and Execute all write here. Do not keep a parallel list in chat.

## Status values

| Status | Meaning | Who |
| ------ | ------- | --- |
| `decided` | A human confirmed a concrete option | Product team (PRD) or technical owner (Techspec) |
| `n/a` | Dimension does not apply to this feature (`N/A because …`) | Agent |
| `open` | Still being clarified **this turn**; blocking | — |

`open` is a working state inside a phase, never a closing one. A phase that still has an `open` row has not finished: ask again ([user-input.md](user-input.md)).

There is no `assumed`. An agent-chosen default is a doubt wearing a decision's clothes — if you would assume it, ask it. The one exception is `n/a`, which is not a guess about what someone wants but a statement that the dimension has no bearing on this feature, and it always carries its `because …`.

## Who resolves what

| Phase | Resolves | Asks |
| ----- | -------- | ---- |
| PRD | Product behavior: what the person sees, chooses, is promised | The product team, in product words ([prd.md](prd.md)) |
| Techspec | The implicit-requirement sweep and every other technical dimension | The technical owner ([techspec.md](techspec.md)) |

A PRD row never contains a mechanism, and a Techspec row never asks the product team to pick one. When a technical dimension has a user-visible consequence, PRD records the consequence and Techspec records the mechanism that delivers it — two rows, linked by topic.

## Implicit-requirement sweep

This sweep belongs to **Techspec**, not PRD. See [techspec.md](techspec.md) — the dimension table lives there, next to the phase that can answer it.

## Discuss rhythm

Follow [user-input.md](user-input.md). Recommend **Guided** unless the user asks otherwise.

| Pace | Cadence |
| ---- | ------- |
| Quick | Lead with a recommended option + rationale; the human accepts or overrides |
| Guided | At most 2 independent questions per batch; dependent questions one at a time |
| Detailed | One decision per batch, dependency order |

Every pace still ends in a human answer. "Quick" means fewer round-trips because the recommendation is good, not that the agent decides alone.

Scope guardrail: discussion clarifies HOW inside the spec boundary. New capabilities go to Deferred Ideas.

A declined gray area ("you decide") is still a `decided` row — record the option you were handed discretion over, and who handed it to you.

## Ledger table

```markdown
## Ambiguity Ledger

| ID | Topic | Status | Resolution | Rationale |
| -- | ----- | ------ | ---------- | --------- |
| AL-01 | [gray area] | decided | [what we will do] | [why — quote the answer] |
| AL-02 | Concurrent editing | n/a | — | single-user CLI, no shared documents |
| AL-03 | Payment provider is down | decided | show the saved cart and let the person retry | product team, 2026-09-28 |
```

Open questions: none — every row is `decided` or `n/a`.

## Closure

Before presenting the spec:

1. Every AC has a single interpretation and a precise expected outcome
2. Every ledger row is `decided` or `n/a` — no `open`, no `assumed`
3. Run `python3 <skill-dir>/scripts/validate_prd.py <feature>` (see [gates.md](gates.md))

# Ambiguity Ledger

Every gray area is **decided**, **assumed**, or **N/A**. Nothing stays silently unclear.

The ledger lives in `spec.md` as `## Ambiguity Ledger`. Discuss, Specify, Design, and Execute all write here. Do not keep a parallel list in chat.

## Status values

| Status | Meaning | Who |
| ------ | ------- | --- |
| `decided` | User confirmed a concrete option | User |
| `assumed` | Agent chose a default + rationale; user may override later | Agent |
| `n/a` | Dimension does not apply to this feature (`N/A because …`) | Agent |
| `open` | Blocking; do not implement that behavior yet | — |

`open` rows cannot survive spec confirmation. Resolve or convert to `assumed` before presenting the spec.

## Implicit-requirement sweep

After the stories are drafted, sweep these dimensions. Bound the sweep to this feature — never invent requirements outside the boundary.

| Dimension | What to cover |
| --------- | ------------- |
| Input validation & bounds | Limits, formats, sanitization |
| Failure / partial-failure | Timeouts, partial saves, rollbacks |
| Idempotency / retry / dedup | Safe retries, duplicate keys |
| Auth boundaries & rate limits | Who can call what, throttle rules |
| Concurrency / ordering | Races, ordering guarantees |
| Data lifecycle / expiry | TTL, archival, deletion |
| Observability | Logs, metrics, tracing hooks |
| External-dependency failure | Fallbacks, timeouts |
| State-transition integrity | Valid transitions, guards |

**Sizing:**

- **Complex / Large:** every dimension → `decided`, `assumed`, or `n/a because …`. No blanks.
- **Medium:** only dimensions obviously present; collapse the rest to one `n/a` row.
- **Small / Quick:** skip the sweep.

## Discuss rhythm

Follow [user-input.md](user-input.md). Recommend **Guided** unless the user asks otherwise.

| Pace | Cadence |
| ---- | ------- |
| Quick | Propose defaults + rationale; user accepts or overrides |
| Guided | At most 2 independent questions per batch; dependent questions one at a time |
| Detailed | One decision per batch, dependency order |

Scope guardrail: discussion clarifies HOW inside the spec boundary. New capabilities go to Deferred Ideas.

Declined or undiscussed gray areas become `assumed` (chosen default + rationale) — never dropped.

## Ledger table

```markdown
## Ambiguity Ledger

| ID | Topic | Status | Resolution | Rationale |
| -- | ----- | ------ | ---------- | --------- |
| AL-01 | [gray area] | decided | [what we will do] | [why] |
| AL-02 | Concurrency | n/a | — | single-threaded CLI, no shared jobs |
| AL-03 | Retry on 5xx | assumed | 3 retries, 200ms backoff | matches existing HTTP client |
```

Open questions: none — all resolved or assumed.

## Closure

Before presenting the spec:

1. Every AC has a single interpretation and a precise expected outcome
2. Every ledger row is `decided`, `assumed`, or `n/a`
3. Run `python3 <skill-dir>/scripts/validate_spec.py <feature>` (see [gates.md](gates.md))

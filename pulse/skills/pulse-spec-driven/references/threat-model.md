# Threat Model Trigger

A threat model is **not** a default phase. Write `.pulse/specs/features/[feature]/threat-model.md` only when a trigger below is present.

## Triggers (any one)

- Authentication, authorization, or session handling
- Payments, money movement, or billing
- Personal data, secrets, tokens, or credentials at rest or in logs
- User-supplied input crossing a trust boundary (upload, query, HTML, shell, SQL)
- Multi-tenant isolation or cross-user data access
- External callbacks, webhooks, or OAuth
- Privilege change (admin, impersonation, API keys)

If none apply, record in the Ambiguity Ledger: `AL-xx | Threat model | n/a | — | no trigger present`.

## Minimum content

```markdown
# Threat Model: [Feature]

## Assets

- [what is valuable]

## Actors

- [who can interact, including anonymous and admin]

## Trust boundaries

- [browser → API → DB → third party]

## Threats

| ID | Threat | Asset | Mitigation | Status |
| -- | ------ | ----- | ---------- | ------ |
| TM-01 | [STRIDE-style or plain] | | [control in this feature] | in-spec / deferred / accepted |

## Non-goals

- [attacks out of scope and why]
```

Mitigations that this feature owns must appear as SHALL criteria or test IDs. Deferred mitigations need a Deferred Idea or follow-up spec — not a silent skip.

During [review.md](review.md), unmatched TM-IDs without tests or explicit acceptance are findings.

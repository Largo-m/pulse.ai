# Pulse architecture

How `pulse-spec-driven` 2.1.0 is assembled. Portable skill: markdown artifacts + Python gates. No daemon.

```mermaid
flowchart LR
  subgraph sizing [Auto-sizing]
    Q[Quick]
    M[Medium]
    L[Large]
    C[Complex]
  end

  subgraph phases [Pipeline]
    S[PRD]
    D[Techspec]
    T[Tasks]
    E[Execute]
    V[Verifier]
    R[Review]
  end

  Q --> E
  M --> S --> E --> V
  L --> S --> D --> T --> E --> V --> R
  C --> S --> D --> T --> E --> V --> R
```

```mermaid
flowchart TB
  User[User decisions] --> Prec[Contract precedence]
  Prec --> Spec[PRD.md]
  Spec --> Surface[surface.md if public]
  Spec --> Tests[tests.md catalog]
  Spec --> Ledger[Ambiguity Ledger]
  Surface --> Techspec[TECHSPEC.md]
  Tests --> TaskGraph[tasks.md + Task Graph]
  Techspec --> TaskGraph
  TM[threat-model.md if trigger] --> Techspec
  TaskGraph --> Impl[Implementer worker]
  Impl --> TaskDone[Task layer: gate + file:line]
  TaskDone --> Verifier[Verifier ≠ author]
  Verifier --> Sensor[Discrimination sensor scratch]
  Verifier --> Val[validation.md]
  Val --> Lessons[Grounded lessons in STATE.md]
  Val --> Metrics[METRICS.md]
  Val --> Review[reviews-NNN if required]
  Review --> Merge[Merge layer]
  SC[Spec Change Protocol] -.-> Spec
  SC -.-> TaskGraph
  SC -.-> Val
  Gates[scripts/validate_*.py] --> Spec
  Gates --> TaskGraph
  Gates --> Val
  Gates --> Metrics
```

## Layers

| Layer | Proof | Role |
| ----- | ----- | ---- |
| Task | Gate exit 0 + assigned test IDs + `file:line` | Implementer |
| Feature | `validation.md` PASS + sensor or labeled fallback | Verifier |
| Merge | No open critical/high review issues | Reviewer, then user |

## What is not in the skill

- Git commits (user policy)
- Compozy daemon / spawn permissions
- Mandatory Idea Factory / council
- Atomic commit-as-law

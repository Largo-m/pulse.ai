# Grounded Lessons

Lessons change future Specify/Design behavior. Opinions about the SDD process itself do not belong here.

## Grounding gate

Record a lesson only from a real signal:

| Signal | Source |
| ------ | ------ |
| `ac_gap` | AC failed or had no `file:line` evidence |
| `surviving_mutant` | discrimination sensor |
| `spec_precision_gap` | AC had no precise outcome |
| `spec_deviation` | `SPEC_DEVIATION` marker |
| `gate_fail` | build/quick/full gate failed |
| `review_valid` | a `valid` critical/high review issue |

No signal → no lesson. A clean PASS records nothing.

## Where

Append to STATE.md `## Lessons Learned` using this shape:

```markdown
### L-NNN: [one terse general rule]

**Signal:** ac_gap | surviving_mutant | spec_precision_gap | spec_deviation | gate_fail | review_valid
**Source:** [file:line or AC id or TM/Issue id]
**Feature:** [slug]
**Status:** candidate
```

Phrase the **title** as a reusable rule, not the incident.

- Yes: `Assert the persisted status value, not that a status field exists`
- No: `The test on line 88 was weak`

## Promotion

- `candidate` — recorded, not loaded as guidance
- `confirmed` — same rule grounded on **two distinct features** → load at Specify and Design
- `quarantined` — confirmed lesson was loaded and the same failure recurred; stop loading it

On Specify and Design, read only `confirmed` lessons relevant to this feature. Keep the set small (context budget).

## Scope

Project-local execution lessons only. Do not auto-write "we should always discuss earlier" — that is a skill maintainer change.

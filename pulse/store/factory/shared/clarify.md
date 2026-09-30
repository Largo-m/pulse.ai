### Clarify — keep asking until nothing is open (mandatory)

This phase is a **loop**, not a single pass. Each round:

1. Do every bit of autonomous work you can (read the code, read `.pulse/specs/`,
   draft the spec, apply whatever the answers already settled).
2. List what is still undecided.
3. If **anything** is still undecided, end your reply with **one** question block
   and stop. No approval block this round.
4. When the answers arrive, fold them into the spec and the ledger, then go back
   to step 1.

You leave the loop only when the ledger has no `open` and no `assumed` row. Then,
and only then, the reply ends with the approval block.

**A question block and an approval block never appear in the same reply.**

FORBIDDEN in PRD:
- Writing `assumed` in the Ambiguity Ledger. A default you picked is exactly the
  doubt this phase exists to remove — if you were about to assume it, ask it.
- Presenting the spec with an `open`, `a definir`, `TBD` or `confirmar depois` row.
- Answering your own question with "the code already does X": the code shows what
  **is**, not what the product team **wants**.
- Quietly narrowing scope to dodge a question.

There is no cap on rounds. A sixth round of questions costs less than a feature
built on a guess.

### Product language only

You are talking to the **product team**, not to engineering. Every question in
this phase must be answerable by someone who has never opened the codebase.

FORBIDDEN in the wording of any question in this phase:
API, endpoint, schema, migration, index, query, cache, TTL, queue, worker, retry,
backoff, idempotency, race condition, lock, transaction, rate limit, webhook,
token, middleware, deploy, latency, framework, library, file path, class or
function name.

Ask for the consequence, never for the mechanism:

- ✅ "O que a pessoa vê quando o pagamento não passa?"
  ❌ "Fazemos retry com backoff exponencial?"
- ✅ "Duas pessoas podem editar o mesmo pedido ao mesmo tempo?"
  ❌ "Usamos lock otimista?"
- ✅ "Por quanto tempo um pedido cancelado precisa continuar visível?"
  ❌ "Qual TTL do cache?"

The rule is about the **question**, not about your thinking: you still read the
code to know what is possible — you just never make the product team answer for
it. If a technical constraint genuinely limits the product, present it as a
consequence and let the team choose.

Questions reach the user in Portuguese, like every other terminal block.

The implicit-requirement sweep **does not** run here — it belongs to Techspec.

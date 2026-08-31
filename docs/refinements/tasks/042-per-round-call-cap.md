# The per-round cap on distinct calls

**Status:** landed 2026-07-16
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

This is the one shape the pool and salience both leave open,
and this entry, its own ADR, and the index warning all had the diagnosis exactly right: it is a
**context-growth** problem rather than a reach one. Every call a round emits costs an appended
`Role.TOOL` message whether it ran, was refused as a repeat, or was refused past a closed pool,
so a round of a thousand calls was a thousand messages fed straight back into the next inference
at a cost of one dispatch when they were identical (salience refuses the duplicates) and of zero pool
when the pool had closed (the budget refuses them and still appends). A cap on the calls
*dispatched* would therefore have bounded nothing, since the refusal is appended too. The cap is
`MAX_CALLS_PER_ROUND` (16, half of `MAX_TOOL_DISPATCHES`) in a new pure-core `tool_round.py`,
and it works by **dropping**: `plan_round` cuts a round to the cap plus one **overflow slot**,
the assistant message's own `tool_calls` truncated with it so the conversation stays well formed
(one `Role.TOOL` answer per `tool_call_id`), and everything past the slot appends nothing at
all. The slot is refused as `ROUND_OVERSIZED_MSG`, which names the cap and invites the next
reply, because a truncation the model **cannot observe** is the one failure a cap must not
create: it would re-emit the dropped calls every round until the round bound ran out. Three
boundary behaviours were rejected: refusing the whole round (drops work the model may still
need and grows the context by a refusal per call), truncating without telling the model (the retry-forever
failure), and a per-call refusal result (bounds the reach the pool already bounds, not the
growth). "**Distinct**" was read as *calls emitted*, not distinct names or `(name, arguments)`
pairs: growth is driven by emission regardless of identity (a round of 200 identical calls still
appended 201 messages though salience let one through), so the cap counts emitted calls and, by
construction, does **not** depend on the separate structural-argument-identity entry above. Half
of `MAX_TOOL_DISPATCHES` on purpose: a model chooses a round's calls before seeing any of that
round's results, so a blind burst that could spend the turn's whole reach is strictly worse than
one that must stop and read halfway, and two rounds at the cap exhaust the default pool. Refused
ahead of both other bounds (the slot reaches nothing, so it is charged nothing and lights no
chip), audited like every dispatch. CI-gated at 100% line and branch over the fakes and
mutation-proven (the truncation, the kept slot, the boundary, the overflow flag, the refusal,
its ordering ahead of the budget, and the assistant-message truncation each reverted
individually to a distinct failing test), and **live-validated** 2026-07-16: a real Qwen3.5-4B on
the GPU, asked over the reference filesystem sidecar to read more files than the cap in one
reply, emitted an oversized round, was truncated to the cap plus one refusal, and read the
refusal to fetch the rest over further rounds. Nothing behind this one; the adjacent
refinements (structural argument identity, the salience limit knob, cross-loop salience) stay as
listed above.

## Trail

- 2026-07-16: Recorded in the ADR-0009 round-cap addendum. The entry, its ADR, and the index's own
  opening warning had all diagnosed it correctly for once, as a context-growth problem rather than
  a reach one, and it closed by dropping a round's calls past a cap rather than refusing them,
  since a refusal is appended to the context exactly as a result is. Nothing opened behind it.

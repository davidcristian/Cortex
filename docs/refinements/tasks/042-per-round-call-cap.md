# The per-round cap on distinct calls

**Status:** done 2026-07-16
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The one form the dispatch pool and salience both leave open, and the diagnosis was right: it is a
context-growth problem rather than a reach one. Every call a round emits costs an appended
`Role.TOOL` message whether it ran, was refused as a repeat, or was refused past a closed pool, so
a round of a thousand calls was a thousand messages fed straight back into the next inference, at
a cost of one dispatch when they were identical and of nothing at all once the pool had closed. A
cap on the calls dispatched would therefore have bounded nothing, since the refusal is appended
too.

The cap is `MAX_CALLS_PER_ROUND` (16, half of `MAX_TOOL_DISPATCHES`) in a new pure-core
`tool_round.py`, and it works by dropping. `plan_round` cuts a round to the cap plus one overflow
slot, truncating the assistant message's own `tool_calls` with it so the conversation stays well
formed with one `Role.TOOL` answer per `tool_call_id`, and everything past the slot appends
nothing. The slot is refused as `ROUND_OVERSIZED_MSG`, which names the cap and invites the next
reply, because a truncation the model cannot see is the one failure a cap must not create: it
would re-emit the dropped calls every round until the round bound ran out.

Three boundary behaviours were rejected: refusing the whole round (drops work the model may still
need and grows the context by a refusal per call), truncating without telling the model (the
retry-forever failure), and a per-call refusal result (bounds the reach the pool already bounds,
not the growth).

"Distinct" was read as calls emitted, not distinct names or `(name, arguments)` pairs, because
growth is driven by emission regardless of identity: a round of 200 identical calls still appended
201 messages even though salience let one through. So the cap counts emitted calls and does not
depend on [R-043](043-structural-argument-identity.md). Half of `MAX_TOOL_DISPATCHES` on purpose:
a model chooses a round's calls before seeing any of that round's results, so a blind burst that
could spend the turn's whole reach is worse than one that must stop and read halfway, and two
rounds at the cap exhaust the default pool. The slot is refused ahead of both other bounds, so it
reaches nothing, is charged nothing and lights no chip, and it is recorded in the audit like every
dispatch.

Covered at 100% line and branch over the fakes, with the truncation, the kept slot, the boundary,
the overflow flag, the refusal, its ordering ahead of the budget, and the assistant-message
truncation each reverted individually to a distinct failing test. Validated live on 2026-07-16: a
real Qwen3.5-4B on the GPU, asked over the reference filesystem sidecar to read more files than
the cap in one reply, emitted an oversized round, was truncated to the cap plus one refusal, and
read the refusal to fetch the rest over further rounds.

## History

- 2026-07-16: Recorded in ADR-0009 decision 13. It closed by dropping a round's calls past a cap
  rather than refusing them, since a refusal is appended to the context exactly as a result is.
  Nothing opened behind it.

# Confirm-with-provenance for tainted turns

**Status:** declined 2026-07-16
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Once untrusted content enters a turn, an outbound tool call is refused outright. The proposal was to
show the user where the content came from and let them approve it knowingly. It waited on structured
provenance, which arrived as `TurnStamp.sources`
([ADR-0027 decision 5](../../adr/ADR-0027-turn-provenance.md)), and the decision is to keep the
refusal.

Read against the code first: `ToolDispatcher.dispatch` (`cortex_core/dispatch.py`) returns
`DENIED_MSG` whenever `stamp.tainted`, and the confirmer is never consulted
(`test_a_tainted_turn_blocks_a_confirm_required_tool_a_confirmer_would_approve` asserts
`confirmer.requests == ()` with an approving confirmer). So there is no card on this path to add a
source line to.

Two independent reasons to keep it. The refusal is a deterministic guarantee rather than a
provenance gap: a tainted turn's arguments may be written by an injection, and a send demanded by
injected content must never be one approval away (`cortex_core/untrusted.py`). A source line does not
change what the card asks a user conditioned to approve to do, and at worst it implies the system
vetted the action. And the refusal is not over-broad, since the legitimate read-then-reply flow still
completes in a fresh turn, taint being turn-local and `DENIED_MSG` saying to ask again, so keeping it
costs one extra turn.

The useful provenance was also absent when the decision was made: only the two attested producers
existed (`SourceKind.TOOL` in `cortex_core/tool_loop.py`, `SourceKind.MEMORY` in
`cortex_core/engine.py`), so a card built then would have named the user's own tool use rather than
the attacker. A `SENDER` producer that would name the attacker arrived later the same day, but a
producer alone does not reverse a fail-closed decision.

It reopens only if the outbound-on-tainted decision is itself revisited with evidence that a card
turns reflexive approval into scrutiny, not on provenance plumbing alone.

## History

- 2026-07-15: Extracted from the roadmap's deferred-refinements section.
- 2026-07-16: Declined. This was the first entry the new structured provenance unblocked, and the
  decision went against building. One of the two reopen conditions, a `SENDER` producer that names
  the attacker, was met later the same day; the other is not.

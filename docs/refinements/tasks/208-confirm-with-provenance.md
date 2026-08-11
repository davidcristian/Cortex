# Confirm-with-provenance for tainted turns

**Status:** declined 2026-07-16
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

The tainted branch is an unconditional block; a
provenance-showing confirmation (so the user can knowingly approve) needs structured
provenance first (the ADR-0013/0019 deferral; its `TurnStamp` seam landed 2026-07-13,
[ADR-0027](../../adr/ADR-0027-turn-provenance.md), the source fields still pending). It also
reverses a deliberate fail-closed posture, so it is revisited as a decision, never slipped
in as plumbing. Until then, re-ask in a fresh turn.
The decision is recorded at the [ADR-0022 confirm-with-provenance
addendum](../../adr/ADR-0022-email-write-confirmer.md).
The source fields the entry waited on landed (`TurnStamp.sources`, [ADR-0027 addendum](../../adr/ADR-0027-turn-provenance.md)),
so the decision it always was could finally be made, and it is a decision to keep the block.
Read against the code first: `ToolDispatcher.dispatch` (`cortex_core/dispatch.py`) returns
`DENIED_MSG` on a gated call whenever `stamp.tainted`, and the confirmer is **never consulted**
(`test_gated_tool_on_a_tainted_turn_is_blocked_even_when_a_confirmer_would_approve` asserts
`confirmer.requests == ()` with an approving confirmer, run green this session). So the posture
is a hard block, not a confirm-without-provenance, and there is no card on this path to add a
source line to. Reversing it is rejected for two independent reasons. **The block is a
deterministic guarantee, not a provenance gap:** after untrusted content enters a turn the
outbound surface is closed, full stop, because a tainted turn's arguments may be
injection-authored and a send demanded by injected content must never be merely a confirm-away
(`cortex_core/untrusted.py`); a source line does not change what the card asks a user conditioned
to approve to do, and at worst launders the action by implying the system vetted it. The posture
is **not over-broad**, since the legitimate read-then-reply flow still completes in a fresh turn
(taint is turn-local, `DENIED_MSG` says to re-ask), so keeping the block costs one extra turn, a
cost the ADR already accepted, while reversing it reopens the exact path an injection aims for.
**And the useful provenance was absent when the decision was made:** at the time only the two
attested producers existed (`SourceKind.TOOL` in `cortex_core/tool_loop.py`, `SourceKind.MEMORY` in
`cortex_core/engine.py`), so a card built then would name the user's own tool use, not the attacker.
A `SENDER` producer that would name the attacker landed later the same day (the sidecar-declared
sender in [untrusted-content.md](../index.md#untrusted-content)), but a producer alone does not reverse a
fail-closed decision. This is the same fail-closed philosophy as the same-day decline of summarizing
a tainted exchange: a provenance card makes the **user** the injection target, worse than the model.
Reopens only if the outbound-on-tainted decision is itself revisited with evidence that a card
converts reflexive approval into scrutiny, now that a real `SENDER`/`URI` producer exists, not on
provenance plumbing alone.

## Trail

- 2026-07-15: extracted from the ROADMAP's deferred-refinements section with the entry kept
  verbatim.
- 2026-07-16: declined, and the area count went from 6 to 5. This was the first entry the landed
  structured provenance unblocked, and the decision went against building. The index records this
  decline as the first reads-against-the-code correction of a Confirmer premise made that day, and
  the session read seam's deletion/rename/pinning entry, whose gated-Confirmer framing it found
  wrong for a management RPC, as the second. The provenance actually captured is attested
  (`TOOL`/`MEMORY`), which names the user's own tool use rather than the attacker; the `SENDER`
  kind that would name the attacker gained a producer later the same day (the sidecar-declared
  sender), so one of the two reopen conditions is now met and the other is not.

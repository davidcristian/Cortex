# A settled handoff record does not say whether the answer was cut

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-14
**Trigger:** the first request to count cut handoffs, or to tell a clean handoff from a cut one
after the log has rolled

Opened 2026-09-14 by the close of
[R-340](340-the-deep-phase-cannot-see-a-cut-call.md), which stopped the deep phase settling a cut
tool call as a machine failure. It now settles `DONE`, which is the right state and carries less
than the old wrong one did: `FAILED` came with a `failure` sentence on the record, and `DONE`
carries no field at all.

So a handoff whose answer a token limit cut and one that finished cleanly are the same record. The
difference lives in two places that both expire. The reply text carries the note, which survives in
the session history for as long as the session does, and the `WARNING` from
`cortex_core.brain_phase` carries `capped`, which survives until the log rolls. Neither is the
record, and the record is what the swap runbook tells an operator to read after a restart.

Nothing needs this yet. No consumer counts handoffs by outcome, and the diagnosis path the runbook
describes reaches the log first. It would bite the first time somebody asks how often the deep tier
is running out of room, which is the question the whole cut-call arm exists to make answerable, and
answering it off a rolling log means answering it for this week only.

The cheap shape is a field on the record beside `failure`, written on the same non-raising path
that leaves `failure` unset, so a settled record says `done` and says whether it was cut. The cost
is a `HandoffRecord` field and the store's serialization, which is why it is not done on
speculation.

## Trail

- 2026-09-14: Opened by the close of
  [R-340](340-the-deep-phase-cannot-see-a-cut-call.md). Recorded in the ADR-0005 deep-cut addendum.

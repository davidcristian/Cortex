# A settled handoff record does not say whether the answer was cut

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-19
**Trigger:** a consumer in this tree reads a settled handoff's outcome: code that counts handoffs
by outcome, or a runbook step that tells a clean `done` record from a cut one

Opened 2026-09-14 by the close of
[R-340](340-the-deep-phase-cannot-see-a-cut-call.md), which stopped the deep phase settling a cut
tool call as a machine failure. It now settles `DONE`, which is the right state and carries less
than the old wrong one did: `FAILED` came with a `failure` sentence on the record, and `DONE`
carries no field at all.

So a handoff whose answer a token limit cut and one that finished cleanly are the same record. The
difference lives in two other places. The reply text carries the note, which survives in the
session history for as long as the session does, but it is the sentence every capped reply
carries, so it does not say the deep tier wrote it. The `WARNING` from `cortex_core.brain_phase`
carries `capped`, which survives until the log rolls. The record is the shortest-lived of the
three: a terminal record is written under `_TERMINAL_TTL_SECONDS`, 3600, in
`cortex_session/handoffs.py` (ADR-0030 decision 4), and the swap runbook sends an operator to it
for that diagnosis hour.

Nothing needs this yet. No consumer counts handoffs by outcome, and the diagnosis path the runbook
describes reaches the log first. It would bite the first time somebody asks how often the deep tier
is running out of room, which is the question the whole cut-call arm exists to make answerable.

The cheap shape is a field on the record beside `failure`, written on the same non-raising path
that leaves `failure` unset, so a settled record says `done` and says whether it was cut. The cost
is a `HandoffRecord` field and the store's serialization, which is why it is not done on
speculation. That field answers whether one handoff was cut, for an hour after it settled. It does
not answer how often: a count over settled records is a count over the last hour, shorter than the
log already covers. The how-often question needs a count kept outside the expiring record, which
is a store's port and its contract test rather than a field.

## Trail

- 2026-09-14: Opened by the close of
  [R-340](340-the-deep-phase-cannot-see-a-cut-call.md). Recorded in the ADR-0005 deep-cut addendum.
- 2026-09-19: the trigger has not fired, and the entry was wrong about which place lasts. It set
  the record against two places that expire, but the record expires first: `put` writes a terminal
  record with `ex=_TERMINAL_TTL_SECONDS`, an hour, and the runbook's own paragraph on reading it
  says "for the diagnosis hour". So the cheap field answers the per-handoff question inside that
  hour and cannot answer the how-often question the entry named as its bite, and the body now
  separates the two. The trigger named a person's request, which the tree cannot show, and now names
  a consumer. The rest holds: `HandoffRecord` still has `failure` as its only settled field, the
  conductor still settles a cut handoff `done` (`swap_conductor.py`), `brain_phase.py` still logs
  `capped` on the warning, and the store reads a record's state only to tell terminal from live,
  for the TTL and the active pointer, so no code counts or reports records by outcome.

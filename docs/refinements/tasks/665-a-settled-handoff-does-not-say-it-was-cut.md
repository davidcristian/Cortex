# Nothing records whether a settled handoff's answer was cut

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)
**Verified:** 2026-10-07
**Trigger:** a consumer in this tree asks how often a deep answer was cut: code that counts
handoffs or deep completions by how they stopped, or a runbook step that asks an operator that
question. On 2026-10-03
`grep -rn 'HandoffState\.\(DONE\|FAILED\)' brain/packages/*/src scripts` prints five lines, the
terminal set, three settling writes and the check that deletes a `done` record, and none of them
counts; the swap runbook reads a record only when it is `failed`.

The deep phase settles a handoff whose tool call a token limit cut as `DONE` rather than
`FAILED` (decision 15 of ADR-0048), and a handoff whose prose answer a limit cut settles `DONE` as
well. A `DONE` record does not outlive that settle. `HandoffSettler._settle` in `swap_settle.py`
deletes the record as soon as it writes `DONE`, which frees the active pointer, so a finished
handoff leaves no record (decision 2 of ADR-0030). Only a `failed` record is kept, for
`_TERMINAL_TTL_SECONDS`, 3600, in `cortex_session/handoffs.py`.

So a cut is written in two places, and nothing counts either. The reply ends with the capped
note, which stays in the session history for as long as the chat does, but every capped reply gets
that sentence, so it does not say the deep tier wrote it. A cut tool call also logs the `WARNING`
from `cortex_core.brain_phase` with `capped`. A cut prose answer logs nothing: `cap_note` only
appends the note, and the deep phase's decode rate line has no `capped` field.

Nothing needs this yet. It would matter the first time somebody asks how often the deep tier runs
out of room, which is the question the cut-call work exists to make answerable.

**What would close it.** A field on the handoff record cannot, because the record is deleted in
the same settle that would write it. The question needs either `capped` on a line every deep phase
writes, such as the decode rate line, so the log answers it for as long as the log is kept, or a
count kept outside the handoff store, which is a port, a fake and a contract test.

## History

- 2026-09-14: opened by the close of
  [R-340](340-the-deep-phase-cannot-see-a-cut-call.md). Recorded in ADR-0048.
- 2026-09-19: the trigger has not fired, and the entry was wrong about which place lasts. It set the
  record against two places that expire, but the record expires first: `put` writes a terminal
  record with `ex=_TERMINAL_TTL_SECONDS`, an hour, and the runbook's own paragraph on reading it
  says "for the diagnosis hour". So the cheap field answers the per-handoff question inside that
  hour and cannot answer the how-often question, and the body now separates the two. The trigger
  named a person's request, which the tree cannot show, and now names a consumer. The rest holds:
  `HandoffRecord` still has `failure` as its only settled field, the conductor still settles a cut
  handoff `done` (`swap_conductor.py`), `brain_phase.py` still logs `capped` on the warning, and the
  store reads a record's state only to tell terminal from live, so no code counts or reports records
  by outcome.
- 2026-09-28: Not fired: nothing counts records by outcome, and the swap runbook still says nothing
  reads the reason back. A deep phase whose prompt outgrew the context now raises
  `ContextOverflowError`, so it settles `failed` with the engine's answer as `failure`, while a cut
  answer still settles `done` with no field.
- 2026-10-03: Not fired, and the entry was wrong about its own subject: a `done` record is not
  kept for an hour, it is deleted. `_settle` (`swap_settle.py:42`) calls `_release_claim`, which
  deletes the record, whenever it writes `DONE`, so only a `failed` record lives out
  `_TERMINAL_TTL_SECONDS`, and the proposed field would have been deleted with the record it was
  written to. The entry also said the `WARNING` with `capped` covers a cut answer; it covers only a
  cut tool call, and a deep prose answer a limit cut logs nothing. The remedy now names a log field
  or a count outside the store, and the trigger names the command that answers it. The tier-scale
  handoffs drawn on 2026-10-02 through `just rpc-handoff` read the client's status events and the
  reply, never a record, and their readings name no capped reply, so they do not bear on it. The
  rule that deletes a finished record is decision 2 of ADR-0030, not decision 4.

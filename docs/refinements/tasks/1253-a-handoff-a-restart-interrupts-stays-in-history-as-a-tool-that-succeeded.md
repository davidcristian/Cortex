# A handoff a restart interrupts stays in history as a tool that succeeded

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-11-18

Boot recovery marks a handoff that a restart of the brain interrupted `FAILED` on its record and in
the log (`_fail_stranded_handoff` in
[swap_recovery.py](../../../brain/packages/core/src/cortex_core/swap_recovery.py)). It writes
nothing to the session. The turn that asked for the handoff is already in history as the cortex's
sentence with `Tools run: escalate_to_brain (succeeded)`, so the next turn reads a handoff that
succeeded, and the person is never told that the question was not answered.

Drawn live on 2026-11-18 on the default stack with escalation on, the Qwen3.8-27B Q4 deep tier and
the model host on build `b12375` (script `crash.sh` and log `logs/crash.txt` in
`~/.cache/cortex-run/2026-11-18/slot11/`). A fact was stored, a handoff was asked for, and the
brain's container was killed once the deep tier answered `ready`, with the cortex and both GPU
subagent servers stopped. The brain was then started again:

- It logged `a handoff did not survive the restart; marking it failed` and `stopping a model left
  running by an interrupted handoff`. The model host stopped the deep tier and started the cortex
  and both servers, and every tier but the deep one answered `ready`.
- The stored fact was recalled, so nothing an earlier turn had stored was lost.
- Asked `What did I last ask you to hand to the deep model, and did it finish?`, the cortex
  replied that the `escalate_to_brain` tool succeeded and that "the task has been completed". The
  question that was handed over has no reply anywhere.

[R-112](112-resume-crashed-handoff.md) leaves the resume for later because "the user asks again",
which needs the user to be told.

What would close it: boot recovery appends a note to the session of the record it fails, through
the `SessionStore` port, saying that the handoff of that brief did not finish and has no reply.
The record has the session id and the brief. The note is true on every turn it reaches, so it
needs no reader of intent. A test over `recover_handoffs` with the fake stores reads the note back
from the session, and the live kill is drawn again.

## History

- 2026-11-18: filed from a live kill of the brain in the middle of a handoff.

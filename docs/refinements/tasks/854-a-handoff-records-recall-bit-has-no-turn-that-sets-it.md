# A handoff record's recall bit has no turn that sets it

**Status:** open, waiting for its trigger
**Area:** untrusted-content
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md) decision 8
**Trigger:** a turn that recall alone tainted calls `escalate_to_brain` and is shown its card.
**Verified:** 2026-10-13

A handoff record stores the ledger's `recalled_only`, so the deep phase allows a task and words a
blocked send as the cortex phase would. Unit tests cover it, and no live turn can reach it today.
Recall taints a turn while its messages are assembled, before any call, and the dispatcher blocks
every confirmed tool on a tainted turn except a record card. `escalate_to_brain` needs
confirmation and is not a record card, so a recall-tainted turn's call returns `RECALL_DENIED_MSG`
and no handoff record forms. The row is in
[recall-tainted task](../../readings/recall-tainted-task.md#a-recall-tainted-turn-asked-to-hand-off).

## What to do

When the trigger fires (for example through a way out of R-848, or escalation becoming allowed on
a recall-tainted turn), drive one such turn on a stack with the deep tier named: memory holding only
tainted rows, the card approved, and the deep model asked to schedule a background task and then
to send an email. The stored bit holds when the task call returns `ok` and is stored tainted, and
the send returns `RECALL_DENIED_MSG`.

## History

- 2026-10-13: filed from the live check of the change that stores the bit in a handoff record:
  the recall-tainted turn's `escalate_to_brain` call was blocked with no card, so the record the
  change is about did not form.

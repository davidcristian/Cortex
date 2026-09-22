# The fired schedule item has two field names across the brain's own log lines

**Status:** done 2026-08-24
**Area:** scheduling
**Origin:** [ADR-0046](../../adr/ADR-0046-work-identities-on-log-lines.md)

The audit trail names a fired schedule item `item_id` on the fire's own dispatch and on every
dispatch its delegate makes, so one grep reaches the fire and the work it caused. The ticker's own
lines about that same fire use a different name. `ScheduleTicker` writes three `_logger` records
under `extra={"reminder_id": ...}`: the fire that failed and will run again on the lease, the
release that failed, and the push that fell back to pull. So `grep item_id=t1` reaches the tool
calls and misses every line the ticker wrote about `t1`, and `grep reminder_id=t1` reaches those
three and no tool call.

Neither name is wrong where it stands. `reminder_id` is the name the interface uses
(`ReminderPost.reminder_id`), which is what the body is handed; `item_id` is the name the stamp and
the audit record use, chosen in ADR-0009 decision 16 as a work identity beside the chat, the turn
and the task. The cost falls on a reader at the moment reading is hardest: a fire that went wrong
is the case where both sets of lines matter.

This is the same shape as [339](339-two-names-for-one-conversation-across-the-brains-log-fields.md). Renaming the ticker's
field to `item_id` makes the grep complete but puts a name on the line that does not match the
message the line is about, while putting both fields on those three records duplicates a value the
formatter renders every time.

## History

- 2026-08-23: opened by the close of
  [380](380-a-fires-delegates-do-not-name-the-item.md), which made one grep by item reach a fire
  and the work it caused, and so made the lines it still misses worth naming. Recorded in ADR-0009
  decision 16.
- 2026-08-24: closed as the rename to `item_id`, decided together with
  [339](339-two-names-for-one-conversation-across-the-brains-log-fields.md) under one rule: a line names a work identity with
  the dispatch stamp's own name for it. The objection this entry raised does not survive a reading
  of the tree. Two of the ticker's three lines are about a fire that never reached the interface at
  all, the fire that failed and the release that failed, so naming them after a message the second
  one rules out was the wrong half to keep. `NotifyRequest.reminder_id` is untouched. The
  `item_id` side was wider than measured here: besides the audit trail,
  `cortex_session/schedule_claims.py` names a schedule item `item_id` on two more lines, the
  quarantine of a corrupt record and the undecodable record on the claim path, and
  [docs/runbooks/scheduling.md](../../runbooks/scheduling.md) prints the second of them verbatim,
  so the split was three lines against three and not three against one trail. The third place this
  entry was waiting for was already in the tree and older than the entry, the swap path's bare
  `handoff` and `turn`, filed as
  [R-415](415-the-swap-path-names-its-work-with-bare-nouns.md). The rename is checked by
  `scripts/logcouplings.py`, whose match for the ticker covers all three of its lines as one set,
  so a fourth arriving under another name makes the check fail; what that registry does not reach
  is a module nobody has listed, filed as
  [R-416](416-a-new-log-line-can-name-its-work-anything.md). Decided in ADR-0046 decision 1.

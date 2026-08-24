# The fired item is spelled two ways across the brain's own log lines

**Status:** landed 2026-08-24
**Area:** scheduling
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The audit trail now names a fired schedule item `item_id` on the fire's own dispatch and on every
dispatch its delegate makes, so one grep reaches the fire and the work firing it caused. The
ticker's own lines about that same fire are not among them.
`ScheduleTicker` writes three `_logger` records under `extra={"reminder_id": ...}`: the fire that
failed and will re-fire on the lease, the release that failed, and the push that fell back to
pull. So `grep item_id=t1` reaches the tool calls and misses every line the ticker wrote about
`t1` itself, and `grep reminder_id=t1` reaches those three and no tool call.

Neither spelling is wrong where it stands. `reminder_id` is the name the seam uses
(`ReminderPost.reminder_id`), which is what the body is handed and what the ticker's lines are
about; `item_id` is the name the stamp and the audit record use, and the named-call addendum chose
it deliberately as a work identity beside the chat, the turn and the task. The cost is only paid
by a reader, and it is paid at exactly the moment the reading is hardest: a fire that went wrong
is the case where both sets of lines matter.

This is the same shape as [339](339-two-spellings-of-one-conversation.md), and the answer wants
the same care: renaming the ticker's field to `item_id` makes the grep whole but puts a name on
the line that does not match the seam message the line is about, while carrying both fields on
those three records is a duplicate the formatter renders on every one. Worth reading the two
surfaces together before picking, since a third one arriving is what this entry is waiting for.

## Trail

- 2026-08-23: Opened by the close of
  [380](380-a-fires-delegates-do-not-name-the-item.md), which made one grep by item reach a fire
  and the work it caused and so made the lines it still misses worth naming. Recorded in the
  ADR-0009 fired-work addendum.
- 2026-08-24: landed as the rename to `item_id`, decided together with
  [339](339-two-spellings-of-one-conversation.md) under one rule: a line names a work identity with
  the dispatch stamp's own name for it. **The objection this entry raised answers itself on the
  tree.** Two of the ticker's three lines are about a fire that never reached the seam at all, the
  fire that failed and the release that failed, so naming them after a seam message the second one
  precludes was the wrong half to preserve; a line is the brain's reading of its own work.
  `NotifyRequest.reminder_id` is untouched. **The `item_id` side was wider than measured here**:
  besides the audit trail, `cortex_session/schedule_claims.py` names a schedule item `item_id` on
  two more lines, the quarantine of a corrupt record and the undecodable record on the claim path,
  and [docs/runbooks/scheduling.md](../../runbooks/scheduling.md) prints the second of them
  verbatim, so the split was three lines against three and not three against one trail. The third
  surface this entry was waiting for turned out to be already in the tree and older than the
  entry, the swap path's bare `handoff` and `turn`, filed as
  [R-415](415-the-swap-path-names-its-work-with-bare-nouns.md). The rename is held by
  `scripts/logcouplings.py`, whose mention of the ticker pins all three of its lines as one set, so
  a fourth arriving under another name reddens; what that registry cannot see is a module nobody
  has listed, filed as [R-416](416-a-new-log-line-can-name-its-work-anything.md). Tabled in the
  ADR-0009 one-vocabulary addendum.

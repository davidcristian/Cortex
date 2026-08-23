# The fired item is spelled two ways across the brain's own log lines

**Status:** open, fix when it bites
**Area:** scheduling
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** an investigation of a fire that reads one spelling and misses the lines carrying the
other, or a third surface spelling the same id under a third name.

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

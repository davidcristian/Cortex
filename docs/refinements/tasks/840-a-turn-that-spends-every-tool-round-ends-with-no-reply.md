# A turn that spends every tool round ends with no reply

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-12

`stream_tool_loop` (`cortex_core/tool_loop.py`) runs at most `MAX_TOOL_STEPS` (8) rounds. When
the eighth round still emits calls, the loop dispatches them and stops without asking the model
again, so the turn has no reply text. `TurnEngine` then stores an empty assistant message, records
the exchange in memory with an empty reply and sends `TurnCompleted` with empty text. Nothing tells
the person what the turn did or that it stopped at a limit: `cap_note` covers only the generation
cap.

Seen on 2026-10-12 in a seeding chat of
[reminder-already-stored.md](../../readings/reminder-already-stored.md): asked "Remind me tomorrow
at 10:00 to check whether the bulb order went out.", the cortex called `list_scheduled`, then
`cancel_scheduled` seven times, one call per round, and the turn ended with an empty reply after
cancelling seven reminders. The chat is `r839-s2a-r11` in the run's scratch logs.

## What to do

Decide what a turn says when its rounds run out: for example, one last inference with no tools
offered, so the model reports what the calls did, or a typed note under the reply naming the limit
and listing each run's tool and outcome. Test it with a scripted backend that emits a call in every
round, and check that the stored message and the memory exchange hold the same text the person saw.

## History

- 2026-10-12: filed from the seeding chats of those readings; the unasked cancels in the same
  chat are [R-837](837-a-cancel-of-a-scheduled-item-needs-no-confirmation.md).

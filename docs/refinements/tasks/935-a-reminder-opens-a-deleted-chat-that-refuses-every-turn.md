# A reminder opens a deleted chat that refuses every turn

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)
**Verified:** 2026-10-29

A scheduled item keeps the `session_id` of the chat that made it, and `delete_session`
(`session_rpc.py`) deletes only the chat and its memories, so a reminder made in a chat that was
deleted later still names that chat. `reminder_to_proto` (`reminders.py`) sends the id, and the
card's `open chat` control (`Reminders.tsx`, `canOpen`) is shown for any id that is not empty and
not the chat on screen (decision 9). Opening it shows an empty chat under the deleted id. Since a
turn sent to a deleted chat is refused, every message typed there now ends as `session_deleted`
("this chat was deleted, so the turn was not answered; start a new chat"); before, it started the
chat again under that id.

Read from the code on 2026-10-29, not run end to end: the shared stack runs with the schedule
backend `none`. The refusal itself is covered by `test_converse_deleted.py`.

## What to do

1. Decide in ADR-0066 what a reminder from a deleted chat offers: no `open chat` (the brain sends
   an empty `session_id` for an id in the deleted set, which the card already handles), or a new
   chat.
2. Reproduce on a stack with scheduling on: make a reminder in a chat, delete the chat, wait for
   the fire, press `open chat`, send a message.

## History

- 2026-10-29: filed from the closing audit of the refusal of a turn sent to a deleted chat.

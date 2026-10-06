# The reminder stack opens only on an empty chat

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md) decision 6
**Verified:** 2026-10-06

`ChatView` opens the stack's `Collapse` on `state.reminders.length > 0 && state.messages.length ===
0` (`body/app/src/components/ChatView.tsx`). The second half arrived in a commit about the panel's
growth on 2026-07-20 and is written down nowhere: the panel test that covers the stack is named
"shows the reminder stack only when something is due, above the scrolling history" and renders
it with no messages, and [runbooks/scheduling.md](../../runbooks/scheduling.md) says the stack
"sits above the history".

On the Linux shell a summon after three reminders had fired showed the chat that scheduled them
and no card, though the pull had returned all three; the cards appeared only after `Ctrl+N`
([readings](../../readings/tauri-ipc-commands.md#attached-pictures-and-reminder-cards)). A
summon shows the chat that was last open, so unless that chat is empty a fired reminder shows
nowhere, and with no body gateway to push a toast, as in this run, the pull is the only delivery.

**Do.** Decide between two readings and record it in ADR-0066 decision 10. Either the stack shows
over any chat, above the history as the test name and the runbook say, with the panel's height
rule settling how a long history and a tall stack share the room; or it stays on the empty chat
and the panel shows that cards wait elsewhere, such as a count on the new chat button. The first
is a one-condition change plus the height case; the second is a visual pick for the maintainer.

## History

- 2026-10-06: filed by the Linux shell run of the reminder pull surface
  ([H-007](../../host/tasks/007-reminder-pull-surface.md)).

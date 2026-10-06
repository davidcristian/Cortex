# A summon over a chat with messages shows no due reminder

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 29 and
[ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md) decision 6
**Trigger:** a History line in this file recording the maintainer's pick of what shows a waiting
card over a chat with messages, from the options in the proposal.
**Verified:** 2026-10-06

The reminder stack is the empty chat's aside (ADR-0035 decision 29): `ChatView` opens its
`Collapse` on `state.reminders.length > 0 && state.messages.length === 0`, and the stack rolls away
when the first message is sent or a chat is opened. The panel test "keeps the reminder stack shut
over a chat with messages" asserts it. The overlay pulls the due cards on each summon (ADR-0066
decision 6), and a summon shows the chat that was last open. So when that chat has messages, the
pull's cards are held in the state and nothing on screen says they are there; they show only after
`Ctrl+N` or the header's new chat button.

On the Linux shell, a summon after three reminders had fired showed the chat that scheduled them
and no card, though the pull had returned all three
([readings](../../readings/tauri-ipc-commands.md#attached-pictures-and-reminder-cards)). With no
body gateway to push a toast, as in that run, the pull is the only delivery. With one, a shown
toast acks its fire ([ADR-0025](../../adr/ADR-0025-scheduling-reminders.md) decision 6), so a
card waits only for a fire whose toast was declined or failed.

## Proposal

What shows a waiting card is a visual pick, so the build waits for it. Each option keeps the cards
themselves as they are.

1. **Recommended: a count on the new chat button.** While cards wait and the chat on screen has
   messages, the header's pencil shows their number, and its label becomes "New chat, 3 reminders
   due". Pressing it, or `Ctrl+N`, opens the empty chat where the stack already stands, with the
   swap motion the stack has today. Nothing shows when no card waits, decision 29 and the panel's
   height rules stay as they are, and the polite notice can say the same line once per pull for a
   screen reader. The cost is a count prop on the header button, its style, and tests.
2. **The stack over any chat.** Drop the empty-chat condition, so the stack stands above the
   history on every chat and leaves when its last card is dismissed. It needs a rule for the
   height: alone, a section takes the whole of the panel's budget (ADR-0035 decision 34), so a
   long stack would take the room the conversation scrolls in. The pull answers after the
   summon's pop, so the stack would also roll open over the conversation as a second movement,
   the motion the stack's chat key was added to remove. Decision 29 would be rewritten.
3. **A summon with cards due opens a new chat.** The summon would start a fresh chat whenever
   the pull returns a card. The pull ends after the panel has placed itself, so the chat would
   swap after the summon as a second movement, and the user would lose the chat they left open,
   which every other summon keeps.

The pick edits ADR-0035 decision 29 for option 2, or ADR-0066 decision 6 for options 1 and 3.

## History

- 2026-10-06: filed by the Linux shell run of the reminder pull surface
  ([H-007](../../host/tasks/007-reminder-pull-surface.md)). The stack's place on the empty chat is
  a decision, so what shows a card over a chat with messages is a pick that waits for the
  maintainer.

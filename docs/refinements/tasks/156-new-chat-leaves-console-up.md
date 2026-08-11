# A new chat leaving the console up

**Status:** landed 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

`Ctrl+N` and the header's
pencil clear the switcher and any pending confirm but not `consoleTab` (`overlay/overlayState.ts`,
case `newChat`), so the panel mints the session and empties the chat *behind* the console while
Appearance or Shortcuts stays on screen. Measured 2026-07-20 at 900x900: open the console from the
hint strip's sliders, blur, press Ctrl+N, and the live tabpanel still reads "Appearance" while the
title behind it has gone back to "New chat". This is older than the console, since the two sheets
it replaced were not cleared by `newChat` either, so the merge neither caused it nor claims
otherwise. The fix is one line in that case arm; which line is the question, and it belongs to the
user rather than to a defect list. A new chat is arguably a request to be in the chat, and the
case arm already puts the panel in `mode: "panel"` for exactly that reason. Against that, the
console is the one surface that is about the app rather than the conversation, and closing it out
from under someone who reached for a new chat while reading the shortcut list is the same
surprise pointing the other way. Nothing else is ambiguous: `dismiss` and Esc both close the
console on purpose and say so in their comments, so this is about the third door alone.
**The user answered on 2026-08-03 and it LANDED the same day
([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)): Ctrl+N closes the console.** A
keystroke aimed at the conversation puts you in the conversation, so the chat is cleared, the tab
goes with the chat it was opened over, and the empty chat is what is on screen. The entry framed
the question correctly and undersold the answer by exactly one arm, which is the usual lesson
here: `openSession` had the identical hole, and its version is reachable by keyboard, because
Ctrl+Up and Ctrl+Down are global keys in `Overlay.tsx` and cycle straight into it while the
switcher row that normally starts a load is `display: none` behind the console. Those two keys and
Ctrl+N are the whole reachable surface, the pointer doors into both arms (the pencil, a switcher
row) being under the console. So "one line in one reducer arm" was two lines in two, and the rule
that shipped is a conversation arriving on the
panel brings the chat with it, rather than a special case for one keystroke. The two chat swaps
that do NOT clear the tab were read at the same time and are unchanged with their reasons now
written down: `deleteSession` keeps it for the same reason it already keeps the switcher open (a
delete comes from a switcher row, so the user is managing chats rather than asking for one) and is
unreachable from the console besides, and `adoptSession` is a cold-start restore that must take
nothing off the panel and cannot meet an open console anyway, a summon having set `touched`. Both
halves are pinned in `overlay/overlayState.test.ts`, the arriving pair walked through both tabs
and both doors, the standing pair asserted as standing, and each arm's clear was proven to redden
its case by being removed in place. Both were also watched in the browser at the entry's own
900x900, before and after, and the readings are in the ADR addendum: with the clears removed the
console is still the live view after each press, and with them in place the chat is.

## Trail

- 2026-07-20: Opened when verifying the console merge put a new chat behind a standing console.
- 2026-08-03: Landed on the user's answer, the area going 19 to 18. It was one of only two entries
  anywhere in the backlog whose blocker was a preference rather than work, and a 2026-08-06
  correction found that only this one ever was, the other having been describing code that no longer
  existed. The count moved by one and the code by two, which is this file's recurring correction.

# The chat cycle keys' silent swap

**Status:** landed 2026-08-04
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened 2026-08-03 by the answer
to the entry above, which settled that `Ctrl+↑` and `Ctrl+↓` are an application-wide cycle rather
than movement inside the switcher and so left them exactly as they were. `Overlay.tsx` calls
`cyclePrev` and `cycleNext` from a window keydown, the whole conversation is replaced, and focus
never moves. Measured in Chromium at 900x900: two presses take the header title from "New chat"
to "Summarize my unread email" to "Everything about model swaps", focus stays on the header's
chats button throughout, the first press closes the switcher out from under the reader, and the
only live region on the page is the link indicator's `role="status"`, which reads the brain's
health and says nothing about the chat. A sighted user sees the panel change; a reader is told
nothing. The listbox shape would have answered this by moving focus, and that shape was rejected,
so what fits is a polite live region naming the chat that arrived (`state.title` already holds
it) rather than a focus move. It wants a look at the other paths into the same swap, a switcher
row and a cold-start restore, so a reader is not read back a title it just clicked. Nothing
blocks it.
- **LANDED 2026-08-04, as the live region this asked for, and the paths were seven rather than
  two** ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). Everything above was
  measured true again at 900x900 before anything was written: the same three titles in the same
  order, focus on the chats button throughout, the switcher closing under the first press, and
  one `role="status"` on the page. The answer is the entry's own, a polite region naming the chat
  that arrived rather than a focus move, and it says `Switched to <title>` because a bare title
  out of nowhere names a thing without saying what happened to it. **Four of the entry's claims
  were wrong, and each one changed the fix.** "The only live region on the page" is true of the
  page as measured and not of the overlay, which has two more that mount conditionally, the
  capture ring (`role="status"`) and an errored reply's bubble (`role="alert"`); neither is ever
  about a chat, so the conclusion stands and the count does not. "`state.title` already holds it"
  holds only AFTER the swap: a history load can fail and its `.catch` leaves the current chat in
  place, so a notice raised at the keypress would name a chat that never arrived, and what ships
  is the title the reducer arm computes off the same `headerTitle` the header takes. The paths
  are seven rather than "a switcher row and a cold-start restore", and two of the ones it missed have
  the identical defect: `Ctrl+N` replaces the conversation with an empty one just as silently,
  and so does the fresh chat that lands when the open chat is deleted (both measured). And the
  rule cannot be decided in the reducer arm at all, because one arm serves two paths each
  (`openSession` is the row and the keys; `newChat` is the pencil and `Ctrl+N`), so the flag
  travels with the action from the path that raised it. What speaks: the cycle keys, `Ctrl+N`, a
  reminder's "open chat", and the chat replacing a deleted one. What does not: a switcher row and
  the header's pencil, each already carrying the arriving title as its own accessible name, and
  cold-start adoption, which has no gesture to answer and runs only while `touched` is false.
  Two things the entry did not have. **A path that says nothing CLEARS the notice** rather than leaving it,
  since a removal is not announced under the default `aria-relevant` and the region should hold
  only what was last actually said. **And a title said twice is not said twice**: a live region
  reports a mutation and not a value, so `overlay/notice.ts` carries a count and the region's
  child is keyed on it, measured as three mutations across two `Ctrl+N` presses (an addition, a
  removal, an addition of the identical string) where an unkeyed child mutates nothing the second
  time. The region lives at the overlay's root and not in the panel, which is the placement a
  test pins: the panel is `inert` while dismissed and the cycle keys are global, so a region
  inside it would enter the accessibility tree in the same commit as the words it announces.

## Trail

- 2026-08-03: Opened by the answer to the switcher's role, which settled that the cycle keys are an
  application-wide cycle rather than movement inside the list and left them exactly as they were.
- 2026-08-04: Closed by the live region it asked for, every number in the entry having measured true
  again before anything was written. It was wrong four times over and each one moved the fix. It
  opened the focus entry that follows it.

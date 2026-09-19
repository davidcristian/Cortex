# The chat cycle keys' silent swap

**Status:** done 2026-08-04
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

`Ctrl+↑` and `Ctrl+↓` replaced the whole conversation from a window keydown in `Overlay.tsx`
without moving focus and without announcing anything. Measured in Chromium at 900x900: two presses
took the header title from "New chat" to "Summarize my unread email" to "Everything about model
swaps", focus stayed on the header's chats button, and the first press closed the switcher. A
sighted user sees the panel change; a screen reader user is told nothing.

Fixed with a polite live region at the overlay's root, which says `Switched to <title>`, because a
bare title names a thing without saying what happened to it. It is at the root rather than in the
panel, since the panel is `inert` while dismissed and the cycle keys are global.

Four details in the entry were wrong and each changed the fix.

- The overlay has two more live regions that mount conditionally, the capture ring and an errored
  reply's bubble. Neither is ever about a chat, so the conclusion holds and the count does not.
- `state.title` holds the arriving title only after the swap. A history load can fail and leave the
  current chat in place, so the announcement uses the title the reducer computes, the same
  `headerTitle` the header uses.
- There are seven paths into a swap, not two. `Ctrl+N` and the fresh chat created when the open
  chat is deleted have the identical defect. What announces: the cycle keys, `Ctrl+N`, a reminder's
  "open chat", and the chat replacing a deleted one. What does not: a switcher row and the header's
  pencil, which already have the arriving title as their accessible name, and cold-start adoption,
  which answers no gesture.
- The rule cannot be decided in the reducer case, because one case serves two paths each, so a flag
  travels with the action from the path that raised it.

Two things the entry did not have. A path that announces nothing clears the region, since a removal
is not announced under the default `aria-relevant`. And a title said twice is not announced twice,
because a live region reports a change and not a value, so `overlay/notice.ts` keeps a count and the
region's child is keyed on it; measured as three changes across two `Ctrl+N` presses.

## History

- 2026-08-03: Opened by the answer to the switcher's role, which settled that the cycle keys are an
  application-wide cycle rather than movement inside the list.
- 2026-08-04: Closed by the live region it asked for. Every number in the entry measured true again
  first. It opened the focus entry that follows it.

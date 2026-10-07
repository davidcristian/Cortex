# The conversation cannot be scrolled from the keyboard

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)
**Trigger:** a History line in this file recording the maintainer's pick of A or B.
**Verified:** 2026-10-07

The conversation scrolls in `.history` in `body/app/src/components/ChatView.tsx`, a `div` with no
`tabIndex`, and no key handler in the overlay moves it: `useLogScroll.ts` and `logRoll.ts` set
`scrollTop` only to follow the stream and to roll a section. On the Linux shell on 2026-10-07,
with a reply taller than the window, `Page_Up` in the field changed nothing, and seven presses of
`Tab` from the field went to the send button, the two hint strip buttons and the header's buttons,
never to the conversation ([readings](../../readings/overlay-turn-flows.md#the-keyboard)). A
person without a pointer can read only the end of a long reply. Chromium makes a scroller with no
focusable child a tab stop of its own, so WebView2 may give the conversation one while no
`Thoughts` disclosure is in it; that is an assumption, not run.

## Proposal

- **A. Page keys from the field** (recommended). `PageUp` and `PageDown` in the composer scroll
  the conversation by most of its height, as chat clients commonly do, and leave the draft alone.
  Nothing new is drawn, and the keys join `fieldKeys.ts` and the Chords tab. A draft taller than
  the field then scrolls only by its arrows.
- **B. The conversation as a tab stop.** `tabIndex={0}` and a label on `.history`, so the arrow
  and page keys scroll it once it has focus. It needs a focus ring for the conversation, which is a
  visual pick, and one more stop between the header and the composer.

## History

- 2026-10-07: filed from keyboard use of the overlay on the Linux shell.

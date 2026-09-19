# A swap from a closing section dropping focus

**Status:** done 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

Three controls sit inside sections the swap itself removes: a switcher row, a reminder card's "open
chat", and a delete confirm. The focused control stopped existing and the browser fell back to
`<body>`, leaving the reader outside the panel and one Tab from the top of the page. Nothing was
announced wrongly, since a live region reads regardless of focus.

Where focus belongs after a swap was a decision, so it went to the maintainer with three candidates:
the composer, the header's chats button, or a third answer for the delete confirm. He chose the
composer for all three, because it is where a summon already puts the caret and it puts the reader
in the conversation that arrived.

What shipped is one rule: a conversation arriving on the panel takes the caret with it, as
`OverlayState.arrival`, a count each swap case raises, read by the composer's existing focus effect.
`active: boolean` became `arrival: number | null`, one prop rather than two. No flag travels with
the action, because every path on a case needs the same result; adoption is excluded by being its
own case.

The entry's measurement was right about one path of three. Only the switcher row keeps focus for the
animation (measured at 0, 60, 150, 290 and 320ms, reading `BODY` by 700ms). A reminder card's stack
is keyed on the session id, so a swap remounts it and the control is gone immediately, and a leaving
switcher row is `withdrawn` as soon as `sessions` drops it, and `inert` blurs what it contains. The
paths are also not three: `Ctrl+N` pressed with focus on a switcher row has the same defect, so this
belongs to where the gesture was made rather than to which control made it.

Afterwards every path reads the composer at 0ms and at every sample to 700ms. The panel's motion is
unchanged frame for frame, which is `preventScroll` doing its job.

## History

- 2026-08-04: Opened by the live region above, which left focus alone deliberately.
- 2026-08-06: Closed on the maintainer's answer. It opened two entries behind it: the same rows
  losing focus for gestures that swap nothing, and the draft the caret now arrives in belonging to
  no chat.

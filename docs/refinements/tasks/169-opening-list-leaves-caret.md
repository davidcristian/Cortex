# A list the reader opens leaving the caret behind

**Status:** declined 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened
2026-08-07 by the close above, which settled where the caret goes when a section closes and left
the other direction exactly as it found it. Measured at 900x900: `Ctrl+K` pressed from the composer
opens the switcher and leaves the caret in the field with its draft and selection intact, and the
list it just opened is not adjacent to that field in either direction (six Shift+Tab presses from
the composer walk the example chips, the mark button and both reminder rows without reaching a
switcher row). Opening it with the header's chats button is nearer but not near: the caret is on
the button, and the next three Tab presses are the header's own theme, new chat and dismiss
buttons, the fourth being the first row's title. So a keyboard reader who asks for the chat list is
shown it and left standing away from
it, which is the same complaint the closed entry made about closing, one direction over. The
decision is not obvious and that is why this is an entry rather than a line: moving the caret into
the list on open would pull a reader out of a half typed sentence, which is exactly the hazard the
close rule guards against, and it would have to choose a row (the open chat's, or the first) and
answer what happens when the list is empty. The cheaper shapes are worth weighing first, a header
order that puts the list next to the control that opens it, or nothing at all on the argument that
the reader who wants a row can Shift+Tab once from the composer if the DOM order earns it. Wants
the same trace, `document.activeElement` sampled across the opening roll, plus a tab order walk
written down. Nothing blocks it.
- **CLOSED 2026-08-07 with the caret DECLINED and a sentence landed in its place**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). The trace and the walk came first,
  in headless Chromium at 900x900 against the demo bridge, `document.activeElement` sampled every
  animation frame for 800ms across thirteen doors, the accessibility tree read for what the header
  control itself says, and a `MutationObserver` on every live-region-shaped node.
  **The entry's central claim held and every number in it was wrong.** The caret is untouched by
  an opening list at all thirteen doors, and the composer's half typed sentence keeps its text and
  its offset through one. But the distance is not a property of the design. Walked with the
  keyboard rather than counted from the markup, the six Shift+Tab presses are **ten** on the empty
  state, the walk crossing two example chips, the mark button and three reminder rows before the
  last row's pin; and in a chat that has messages, where none of those are on screen, they are
  **two**. Forward it is nine either way, the walk leaving the document at the hint strip and
  re-entering at the header. Only the headline figure survived: from the chats button, Tab passes
  theme, new chat and dismiss, and the fourth press is the first row's title.
  **And the doors are thirteen where the entry counted two**, this chain's lesson arriving for the
  fourth entry running. The switcher has one opening arm, which is what the entry counted; what a
  rule has to answer is where the caret is standing when it fires, and that is the composer with
  and without a draft, the chats button by pointer and by Enter, `Ctrl+K` from the chats button,
  from the header's theme button, from a reminder's ack, from an example chip, from a hint strip
  opener, from a pending confirm's Deny, from behind an open console, from a tucked panel, and
  onto an empty list.
  **The caret is declined, for three measured reasons.** The first decides it: a guard is not
  optional, because `Ctrl+K` is pressed as often from the composer as from the list, so the rule
  would have to be the mirror of the close rule's, "only when the caret is on the anchor", and the
  anchor is the chats button, whose `aria-expanded` already reports the change under the caret
  that pressed it. Everything the guard lets through is the one door already answered. The second:
  it cannot answer an empty list, there being no row to hand the caret to. The third: it would
  have to choose a row without one being obviously right, since the open chat frequently has no
  row at all, a fresh chat being unlisted until it is written to. **The header reorder is declined
  too**, buying three Tab presses at that same already-answered door by moving the control that
  opens the list to the end of a cluster whose last button is Dismiss, which is a visual change
  made for a reading-order fact.
  **What the measurement found instead is that an opening list is inaudible**, and that is what
  landed. Eleven of the thirteen doors move no caret, change no control the reader is standing on,
  and raise nothing in any live region: the only channel carrying the fact is `aria-expanded` on a
  button the reader is not on, which carries no `aria-controls` and no description either. On an
  empty list the tab order cannot help at all, the line reading `No other chats yet` being text
  inside the `<ul>` rather than a tab stop, so Tab from the chats button walks the header's
  remaining three buttons and leaves the list entirely.
  **So a list the reader opens says what it holds**: `Recent chats open. 3 chats.`, and the
  switcher's own words when it holds none. It is the CONTENTS and not the toggle, which is why
  there is no mirror for closing: a close is answered by the caret landing on the chats button,
  and announcing it as well would say the same fact twice at every close made from inside the
  list. The door decides rather than the arm, as the arriving-chat arms already do, so `Ctrl+K`
  speaks and the header's button does not. And a list that opened where nobody could see it says
  nothing: measured, both chords open the switcher from a tucked panel and from behind an open
  console, its rows mounting where the reader can neither see nor reach them.
  **What it cost**: `overlay/chromeState.ts`, 66 lines holding the switcher's toggle and the
  console's three tab arms, which is the third half split off `overlayState.ts` and for the same
  reason as the other two, that file having stood at 291 lines against a 300-line cap;
  `switcherOpened` in `overlay/notice.ts`, sharing its plural helper with the tally a shrinking
  list reports; `RECENT_CHATS` exported beside `NO_OTHER_CHATS` so the header control, the list's
  own label and the sentence are three renderings of one name; and the flag through
  `useOverlay.toggleSwitcher` to the two doors.
  **After, measured the same way, every door.** The nine keyed doors on the chat now produce
  exactly one `childList` mutation on `.announcer` and nothing anywhere else, the empty list
  reading `Recent chats open. No other chats yet.`; the two button doors and the two doors where
  the chat is not on screen stay silent; and the caret is unmoved on all thirteen, the traces
  frame for frame what they were. Three open-and-close rounds in one page produced three
  announcements, each replacing the region's child with identical text, and the three closes
  between them raised nothing, which is the count key doing its job. The full before and after
  tables are in the addendum.
  **The mutation proof.** Neutering the sentence reddens the reducer's case and the end to end
  one; dropping the door's flag reddens four, the button's silence, the close, the carried notice
  and the end to end case; dropping the on-screen guard reddens the tucked and behind-the-console
  case alone; announcing the close as well reddens the close case alone; counting an empty list
  instead of borrowing the line's words reddens the empty case and the reducer's; and making the
  key's door silent reddens the key's own case and the end to end one. Six mutations, six distinct
  rednesses, nothing else in the 670 test suite moving under any of them.
  One thing opened behind it, below.

## Trail

- 2026-08-07: Opened by the close above, which settled where the caret goes when a section closes
  and left the other direction exactly as it found it.
- 2026-08-07: Closed hours later the same day with the caret declined on three measured reasons and
  the header reorder declined with it, and a sentence landed in its place, a list the reader opens
  saying what it holds. The central claim held while every number in it was wrong, and the doors
  were thirteen where it counted two, the fourth entry in this chain to undercount them. It opened
  the key toggling a section nobody can see.

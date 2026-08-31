# Row gestures that swap nothing dropping focus

**Status:** landed 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened 2026-08-06 by the entry above, whose rule covers only the gestures that replace the
conversation. The same rows reshape and leave for other reasons, and each one loses the caret to
`<body>` (measured at 900x900): pressing Rename swaps the row for its editor and does not put the
caret in the input, committing the rename swaps it back, pressing Delete swaps the row for its
confirm, confirming the delete of a chat that is NOT the open one takes the row away, and acking a
reminder holds focus on the ack for its roll (0 and 150ms) and reads `BODY` at 350. None of them
is a swap, so `arrival` never hears about them, and each needs an answer of its own shape rather
than the composer: a rename editor needs its own input, and a row leaving needs the row that took
its place or the list around it. It is one decision about what a list does with focus when it
changes shape under the hand, plus small wiring per gesture (`SessionList.tsx`, `Reminders.tsx`).
Nothing blocks it.
- **LANDED 2026-08-06 as one rule with three clauses**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). A list that reshapes under the hand
  keeps the caret: a row that changes SHAPE hands it to the control the new shape puts in the place
  of the one that left; a row that LEAVES hands it to the same control in the row that inherits its
  place, below where there is one and above for the last row; and a list with no row left hands it
  to its anchor, a control the view holds outside the list. The decision was the implementer's, the
  entry saying so, and the composite-row reading is what the switcher's own accessibility pass
  forced: those rows are four buttons each and were taken out of `listbox` for exactly that reason,
  so "the next option" has no referent and "the same column, one row down" does.
  **The entry filed five gestures and there are thirteen**, which is the sibling entry's lesson
  repeating one entry later. Measured at 900x900, all thirteen: a rename opening, committing by the
  save button, committing by Enter and cancelling by Escape; a delete opening, cancelling, and
  confirming against another chat, against the last row, against the only row and against the open
  one; a reminder acked, the last reminder acked, and a pin toggled. Nine of them read `<body>` at
  0ms and the mechanism is an UNMOUNT rather than the `inert` the entry above found for its own
  paths: the row's shape change takes the pressed control out of the tree (`pencilInDom` 3 → 2 with
  no slot `inert`), and a confirmed delete unmounts the confirm in the same commit that withdraws
  the row, so `inert` is redundant there rather than the cause. The ack is the one that behaves as
  filed, holding the caret at 0, 150 and 320ms and reading `<body>` at 350. **The pin toggle needs
  no answer**, its button surviving the regroup it causes, focus held at every sample to 700ms.
  **Two findings the entry did not have, both fixed here.** Escape cancelling a rename also
  dismissed the whole panel: the editor closed the editor and the press carried on to the window
  listener, so undoing a rename ended the session (the panel read `panel edge-live`, no `open`,
  400ms later). And `?` typed into that editor opened the console, the global guard naming the
  composer's textarea alone, so "why?" left `why` in the field and the settings pane over the row.
  Both were reachable before and neither by accident, nothing having put the caret in that editor.
  Both of the row's overlays now keep a cancelling Escape to themselves and the guard asks about
  `HTMLInputElement` too.
  **The confirm opens on its cancel, measured rather than argued.** With focus on the confirm's yes
  one further Enter deleted the chat; with focus on its cancel the same press put the row back. The
  pointer has no such hazard (the yes sits at x=633 against the trash's 528).
  **At the commit, not at the end of the roll**, because the control being aimed at was on screen
  all along and waiting would park the caret in two different places for 300ms: on `<body>` for a
  switcher row, on an element animating to nothing for an ack. The panel does not notice, all at
  60Hz: a confirmed delete leaves its box unchanged at top 108 and height 518 over 60 frames; an ack
  runs 108 to 138.5 over 14 distinct boxes with a largest step of 6.14; the last ack, where the
  section leaves and the caret crosses to the composer, runs 196.75 to 274 over 20 with a largest
  step of 11.57; and the arrival rule's own trace is unmoved, a row press running 108 to 274 with a
  largest top step of 25.58 against the 25.56 it landed at. Every `panel.scrollTop` and every log
  `scrollTop` in those four traces is 0, which is `preventScroll` doing its job.
  **What it cost**: `overlay/rowCaret.ts` (`heir`, `caretKey`, `useRowCaret`), the row's three shapes
  split into `components/SessionRow.tsx`, an anchor prop on each list, the composer's field ref moved
  up to `ChatView` so the stack has one, and the switcher's row withdrawal copied onto the reminder
  stack, which the rule needs: with the caret moved on at the commit, an acked row kept two live tab
  stops for its whole roll. One thing left open behind it, below.

## Trail

- 2026-08-06: Opened by the arrival rule above, whose rule reaches only the gestures that replace
  the conversation.
- 2026-08-06: Closed the same evening, the decision being the implementer's, and the area went 11 to
  12 with three names changing while the count moved by one, which is this file's warning that a
  count right by cancellation hides both of its errors: out went these gestures, in came the
  modified chord and the silent shrink. The entry filed five gestures and there are thirteen, the
  same undercount its predecessor made two entries earlier and by the same route, remembering the
  last report instead of reading the component, and the mechanism is an unmount rather than the
  `inert` that predecessor found. Two live defects turned up alongside and were fixed with it,
  neither about focus and both about the same seam.

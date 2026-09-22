# Row gestures that swap nothing dropping focus

**Status:** done 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

The rule above covers only gestures that replace the conversation. The same rows also change shape
and leave for other reasons, and each lost the caret to `<body>`: opening a rename, committing one,
opening a delete confirm, confirming the delete of a chat that is not the open one, and
acknowledging a reminder.

Fixed as one rule with three clauses. A list that changes shape under the hand keeps the caret: a
row that changes shape hands it to the control that takes the place of the one that left; a row that
leaves hands it to the same control in the row that takes its place, below where there is one and
above for the last row; and a list with no rows left hands it to its anchor, a control the view
holds outside the list. The composite-row reading is forced by the switcher's own accessibility
decision, where the rows are four buttons each, so "the next option" has no referent and "the same
column, one row down" does.

The entry filed five gestures and there are thirteen, all measured at 900x900. Nine read `<body>` at
0ms, and the cause is an unmount rather than the `inert` found for the swap paths. The reminder
acknowledgement is the one that behaves as filed, holding the caret to 320ms and reading `<body>` at
350. The hoist toggle needs no answer, since its button survives the regrouping it causes.

The caret moves at the commit rather than at the end of the animation, because the control being
aimed at is on screen all along and waiting would park the caret in two different places for 300ms.

Two live defects turned up alongside and were fixed here. Escape cancelling a rename also dismissed
the whole panel, because the press continued on to the window listener. And `?` typed into that
editor opened the console, since the global guard named only the composer's textarea. Both are
reachable only now that the caret arrives in that editor.

Cost: `overlay/rowCaret.ts` (`heir`, `caretKey`, `useRowCaret`), the row's three shapes split into
`components/SessionRow.tsx`, an anchor prop on each list, the composer's field ref moved up to
`ChatView`, and the switcher's row withdrawal copied onto the reminder stack, which the rule needs:
with the caret moved on at the commit, an acknowledged row kept two live tab stops for its whole
animation.

## History

- 2026-08-06: Opened by the arrival rule above.
- 2026-08-06: Closed the same evening, the decision being the implementer's. The entry filed five
  gestures and there are thirteen, the same undercount its predecessor made, by the same route of
  remembering the last report instead of reading the component.

# A swap from a closing section dropping focus

**Status:** landed 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened
2026-08-04 by the answer above, which put the arriving chat into speech and deliberately left
focus alone. Three doors sit inside sections that the swap itself takes away: a switcher row
(the list rolls shut), a reminder card's "open chat" (the stack rolls away as the history fills)
and a delete confirm (the row leaves). `Collapse` unmounts its child when the roll ends, so the
control that was focused stops existing and the browser falls back to `<body>`. Measured at
900x900 on all three: focus holds on the row for its 300ms roll and then reads `BODY`, and the
same for the other two. Nothing is announced wrongly (a live region reads regardless of focus,
which is why this did not block that answer) and the keyboard is not trapped, but the reader is
left outside the panel and one Tab from the top of the whole page rather than anywhere near the
conversation that just arrived. The fix is a decision about where focus BELONGS after a swap,
not a patch: the composer is the obvious candidate and is what a summon already chooses
(`Composer`'s `active` edge), the header's chats button is the candidate that keeps a reader
who is browsing chats where they were browsing, and a delete has a third answer again since the
switcher deliberately stays open behind it. Cost is small once that is chosen (the composer's
focus effect already exists and would need a second trigger, or the panel would take a ref);
the deciding is the work. Nothing blocks it.
- **LANDED 2026-08-06 on the user's answer, which is the composer, for the delete confirm as well**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). The user was offered the three
  candidates above and took the first plainly: it is where a summon already lands, and it puts the
  reader in the conversation that arrived. What ships is one rule, that a conversation arriving on
  the panel takes the caret with it, as `OverlayState.arrival`, a count each swap arm raises, and
  the composer's existing focus effect reading it (`active: boolean` became
  `arrival: number | null`, one prop rather than two, which is one idea and also what keeps
  `ChatView` at 299 lines rather than standing exactly on its cap).
  **The entry's own measurement was right about one door of three.** Only the switcher row holds
  focus for the roll: measured again at 900x900, the row keeps it at 0, 60, 150, 290 and 320ms and
  reads `BODY` by 700ms. The other two lose it in the commit itself, by two mechanisms the entry
  did not have. A reminder card's stack does not roll away at all, its `Collapse` being keyed on
  the session id, so a swap remounts it and the control is gone at once; and a leaving switcher row
  is `withdrawn` the moment `sessions` drops it, and `inert` blurs what it contains, so the delete
  confirm reads `BODY` at 0ms too. **And the doors are not three.** `Ctrl+N` pressed with focus on
  a switcher row holds it to 290ms and reads `BODY` at 320, so this belongs to where the gesture
  was made rather than to which control made it, and the cycle keys reach it the same way. After,
  every door reads the composer at 0ms and at every sample to 700ms: a switcher row, a reminder's
  open control, a delete confirm on the open chat, `Ctrl+N` from a row, `Ctrl+↓` from the chats
  button, and the header's pencil. **The rule needed no flag, which is the one place this differs
  from the notice it was opened by.** Every door on an arm wants the same landing, so each arm
  answers for its own doors and nothing travels with the action; adoption is excluded by being its
  own arm. And the panel does not notice the caret moving under it: the switcher's roll is frame
  for frame what it was, 108 to 273.19 with the height 518 to 352.81 over 43 frames, the largest
  top step 25.42 before and 25.56 after, and the log's `scrollTop` identical, which is
  `preventScroll` doing the job it was already there for. Two things this leaves behind, both
  below: the same gestures without a swap still drop focus, and the draft the caret now lands in
  still belongs to no chat.

## Trail

- 2026-08-04: Opened by the notice above, which put the arriving chat into speech and left focus
  alone on purpose. It was never named in the area header, and it was then the last entry anywhere
  whose blocker was a preference rather than work.
- 2026-08-06: Closed on the user's answer, which is the composer, for the delete confirm as well,
  and the area went 12 to 13 because it opened two entries behind it: the same rows losing focus for
  gestures that swap nothing, and the draft the caret now lands in belonging to no chat. Two of its
  own claims wanted correcting, both about mechanism, and the doors are not three, any global key
  pressed while focus sits inside the switcher having the identical defect.

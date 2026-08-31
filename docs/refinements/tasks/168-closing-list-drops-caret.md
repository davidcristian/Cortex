# A list the reader closes dropping the caret

**Status:** landed 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened 2026-08-07 by the chord entry above, which closed one of these paths and left the others
standing.
The caret rule answers a row changing shape, a row leaving, and a list running out of rows; a list
the reader closes is none of the three, and the rows are unmounted with it. Measured at 900x900
with the caret on a resting row's pencil and no editor open, `Ctrl+K` left `document.activeElement`
on `<body>`, outside the panel and one Tab from the top of the document, which is the same landing
the caret rule was built to abolish and the same one `Ctrl+K` produced from inside an editor until
today. The answer is not one line, which is why it is here: the switcher closes four ways and two
of them already answer (selecting a row swaps the chat and the arrival rule takes the caret to the
composer, deleting the open chat does the same), so what is wanted is a rule for the other two,
the key and the header's chats button, and it has to move the caret only when the caret is inside
the list, or `Ctrl+K` pressed from the composer would pull the reader out of a sentence. The
anchor the list already carries is the landing (`ChatView` holds it for exactly this reason), and
the reminder stack has the same question with a different answer, its section leaving with its
rows. Wants the same trace the caret rule took, `document.activeElement` sampled across the roll,
before a shape is picked. Nothing blocks it.
- **LANDED 2026-08-07 as a rule about a section CLOSING rather than about a key**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). The trace the entry asked for came
  first, in headless Chromium at 900x900 against the demo bridge, `document.activeElement` sampled
  every animation frame for 800ms across twenty three paths, and **the entry's own reading held**:
  with the switcher open and the caret on a resting row's pencil, `Ctrl+K` kept the caret on that
  pencil for the whole 300ms roll (frames at 1, 21 and 337ms) and read `<body>` at 353ms, outside
  the panel and one Tab from the top of the document. Sampling across the roll rather than after it
  is what showed the mechanism, and it is not the one the entry assumed: nothing is lost at the
  gesture, because `Collapse` keeps its child mounted for the roll, and everything is lost at the
  unmount three hundred milliseconds later.
  **The switcher does not close four ways. It leaves the reader's reach thirteen**, which is this
  chain's lesson arriving for the third entry running, and ten of the thirteen already answered by
  three mechanisms rather than by the entry's one. **Seven are chat swaps** and the arrival rule
  takes the caret to the composer, every one measured: a switcher row, `Ctrl+N`, the header's
  pencil, `Ctrl+↑`, `Ctrl+↓`, a reminder's open control, and a delete confirm on the open chat.
  **Two are the console arriving over the chat**, the `?` key and the hint strip's openers, where
  the console's own selected tab takes the caret in its layout effect (measured at 26ms and 60ms),
  so a section going inert under the caret was already answered one layer up. **One is the header's
  chats button, and the entry was wrong to ask for a rule for it**: measured, the pointer's press
  moves the caret off the row and onto the button at 45ms, before the close is dispatched at all,
  and the keyboard can only press a button the caret is already on. **Two are the panel being
  dismissed**, Escape and the tuck button, where the caret reads `<body>` at 39ms and at 71ms
  because `inert` blurs what it contains, and that is right rather than open: there is nothing on
  screen to hold a caret. **`Ctrl+K` was the whole of what was open**, in three shapes of "inside
  the list" (a row's pencil, a row's title, and an open delete confirm's cancel), all three landing
  on `<body>` by 354ms.
  **The reminder stack has the same gap and it is not the stack's own control.** Its three
  closings: acking the last row, which `useRowCaret`'s anchor already answers (the caret is in the
  composer at 53ms); a swap, which the arrival rule answers; and the first message landing, which
  is reached by two paths. The composer's own send is standing in the field already. The other is
  an **example chip on the empty state**, which is in no list, has no heir, and whose press unmounts
  the whole empty state and rolls the stack away with it: measured, the caret read `<body>` at
  39ms. That one is answered here.
  **The rule: a section the reader closes hands the caret to its anchor, and only when the caret is
  inside the section.** The anchor is the control each section already carries for its emptied case
  (`ChatView` holds both), so "this section cannot keep the caret" has one answer rather than two:
  the header's chats button for the switcher, which is what closed the list and what would open it
  again, and the composer's field for a section whose work is over. The composer was weighed and
  refused for the switcher: no conversation arrived, the reader is in the chat they were already
  in, and landing a close in the text field would make `Ctrl+K` a way into the composer, which is a
  larger move than the reader asked for and is the arrival rule's landing rather than this one's.
  **The guard is what makes it a rule instead of a line**, and the hazard the entry named was
  measured rather than assumed: at HEAD, `Ctrl+K` pressed from a composer holding `half a question`
  with the caret parked at offset 4 left the caret and the selection exactly there, so an unguarded
  close would have introduced the defect rather than missed it. The same guard is why the chats
  button needs no case of its own: the caret is on the anchor by the time the close lands, so the
  rule looks and finds nothing to do.
  **It stands down when a conversation arrived in the same commit**, which is stated in code rather
  than left to effect ordering. The composer's focus is a passive effect and this is a layout
  effect, so the composer would win a race anyway; but the caret would touch the chats button first
  and that is a second focus event a screen reader may read, whichever of the two the browser
  paints. The after trace shows the deferral working: a switcher row selected goes
  `button.switcher-item` at 7ms straight to `textarea[Message]` at 40ms, with no frame on the chats
  button in between.
  **Two decision points for one rule, and the difference is what the section does with its
  children.** The switcher is decided at the transition, because its rows are mounted for the roll
  and "is the caret inside" is readable from the DOM in that commit; the chip is decided at the
  gesture, because the empty state is unmounted in the very commit that submits, so by layout time
  the caret is already on `<body>` and there is nothing left to look inside.
  **What it cost**: `overlay/sectionCaret.ts`, 91 lines holding `handOff` (the focus, with the
  `preventScroll` reason in one place) and `useSectionCaret(section, anchor, open, arrival)`; two
  props on `SessionList`, which hears its own close while it is still mounted; one call in the
  empty state's chips. The reminder stack is deliberately not wired to the hook: every closing it
  has is answered elsewhere, so a hook there would be a rule with nothing to do.
  **After, measured the same way, every path.** `Ctrl+K` from a row's pencil lands on
  `button[Recent chats]` in the first sampled frame (6ms) and holds it to 802ms, and from a row's
  title and from an open confirm's cancel by 18ms. The composer's half typed sentence is untouched,
  caret still at offset 4. The seven swap paths still read `textarea[Message]`, the two console
  paths still read the tab strip, the two dismissals still read `<body>`, the stack's own two acks
  are unmoved, and the example chip now reads `textarea[Message]` at 40ms where it read `<body>`.
  The full before and after table is in the addendum.
  **And the panel does not notice the caret moving under it**, traced at 60Hz with the same close
  run twice, once with the handoff and once with it neutered: 49 frames each, the top edge easing
  108 to 139 over the roll (largest single frame 8.02px) and back to 108 over the 130ms after it,
  the height 518 to 487 and back, seventeen distinct boxes, and every `panel.scrollTop` and history
  `scrollTop` 0 throughout, which is `preventScroll` doing its job. The one 31px step in that trace
  is the frame at 322ms reading the unanimated layout, the `requestAnimationFrame` artefact this
  ADR already documents, and it is in both runs identically.
  **The mutation proof.** Neutering the handoff fails the hook's own case and the end to end one
  (`expected <body> to be <button class="hbtn" ...>`, which is the defect restated); dropping the
  arrival guard fails the stand down case; dropping the inside the section guard fails both the
  unit case and the half typed sentence; removing the chip's handoff fails the chip case alone.
  Four mutations, four distinct failures, nothing else in the 661 test suite moving under any of
  them.
  One thing opened behind it, below, and it is the mirror of this one.

## Trail

- 2026-08-07: Opened by the chord entry above, which closed one of these paths and left the others
  standing.
- 2026-08-07: Closed the same day as a rule about a section closing rather than about a key, one out
  and one in, with the mirror entry opening behind it and every top-level entry in the area walked
  beforehand and agreeing with the index cell one for one. The paths were thirteen where the entry
  filed four, the third entry in this chain to undercount them and the second to be wrong about
  which of them were already answered.

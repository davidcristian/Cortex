# A list the reader closes dropping the caret

**Status:** done 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

The caret rule answers a row changing shape, a row leaving and a list running out of rows. A list
the reader closes is none of the three, and its rows are unmounted with it. Measured at 900x900 with
the caret on a resting row's pencil, `Ctrl+K` kept the caret on that pencil for the whole 300ms
animation (frames at 1, 21 and 337ms) and read `<body>` at 353ms. Sampling across the animation
rather than after it showed the cause: `Collapse` keeps its child mounted while it closes, and
everything is lost at the unmount 300ms later.

The rule that shipped: a section the reader closes hands the caret to its anchor, and only when the
caret is inside the section. The anchor is the control each section already has for its emptied
case, so "this section cannot keep the caret" has one answer: the header's chats button for the
switcher, and the composer's field for a section whose work is over. The composer was refused for the
switcher, because no conversation arrived and putting the caret in the text field would make `Ctrl+K`
a way into the composer.

The guard is what makes it a rule rather than one line, and the hazard was measured: before the
change, `Ctrl+K` pressed from a composer holding `half a question` with the caret at offset 4 left
both exactly there, so an unguarded close would have introduced a defect. The same guard is why the
header's chats button needs no case: the caret is on it by the time the close happens. The rule also
does nothing when a conversation arrived in the same commit, stated in code rather than left to
effect ordering, so the caret never touches the chats button on its way to the composer.

The switcher closes thirteen ways for the reader, not four, and ten were already answered: seven are
chat swaps handled by the arrival rule, two are the console arriving over the chat where the
console's selected tab takes the caret, and two are the panel being dismissed, where `<body>` is
correct because nothing is on screen. `Ctrl+K` in its three "inside the list" shapes was all that was
open. The reminder stack's three closings are all answered elsewhere except one: an example chip on
the empty state, which is in no list and whose press unmounts the whole empty state. That one is
fixed here.

Two decision points for one rule, and the difference is what the section does with its children. The
switcher is decided at the transition, because its rows are mounted while it closes. The chip is
decided at the gesture, because the empty state is unmounted in the commit that submits.

Cost: `overlay/sectionCaret.ts`, 91 lines holding `handOff` and `useSectionCaret(section, anchor,
open, arrival)`; two props on `SessionList`; one call in the empty state's chips. The reminder stack
is deliberately not wired to the hook, since every closing it has is answered elsewhere.

Afterwards `Ctrl+K` from a row's pencil reaches `button[Recent chats]` in the first sampled frame
(6ms) and holds it to 802ms, and from a row's title and an open confirm's cancel by 18ms. The
composer's half-typed sentence is untouched. The example chip now reads `textarea[Message]` at 40ms.

Four mutations, four distinct failures: neutering the handoff fails the hook's own case and the
end-to-end one, dropping the arrival guard fails the deferral case, dropping the inside-the-section
guard fails both the unit case and the half-typed sentence, and removing the chip's handoff fails the
chip case alone. Nothing else in the 661-test suite moved under any of them.

## History

- 2026-08-07: Opened by the shortcut entry above, which fixed one of these paths.
- 2026-08-07: Closed the same day as a rule about a section closing rather than about a key. The
  paths were thirteen where the entry filed four, the third entry in this chain to undercount them.

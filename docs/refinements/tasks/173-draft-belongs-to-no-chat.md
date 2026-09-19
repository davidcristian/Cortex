# The composer's draft belonging to no chat

**Status:** done 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

The composer's field is never unmounted, which keeps a draft alive across a trip to the console and
across a chat swap too. That was always true and easy not to notice while focus fell to `<body>`;
with the caret now put in the field by the swap itself, the first thing a reader meets in the
arriving conversation is a sentence they started somewhere else. Reproduced at 900x900 through
`Ctrl+↓`, a switcher row, `Ctrl+N`, the header's pencil, a delete confirm on the open chat and a
reminder card's open control.

The maintainer chose a draft per chat over clearing on swap, because a half-typed question is work
and swapping away is not a decision to discard it.

`OverlayState.drafts` keys the unsent text by session id and the composer is a controlled field over
the entry for the chat on screen (`overlay/drafts.ts`), so the arriving conversation is handed its
own text in the commit that swaps the transcript: nothing is parked, no effect runs in between, and
no frame can paint the wrong conversation's sentence. It lives in the body's reducer rather than
behind a store port, argued in ADR-0052 decision 11: the rule about state surviving a model swap is
about model processes and KV caches, and what a store would add is survival of a body restart, which
unsent text does not need. It is in the reducer rather than the component because the delete cascade
has to reach it and a swap has to be synchronous, which also leaves a store one hydrate away.

An empty field stores nothing, which is the whole eviction policy; a send clears the draft it sent
and an example chip leaves it alone; typing sets `touched`. The caret arrives at the end of a
restored draft, which is where the next character goes. Measured at both window sizes: a draft left
at offset 2 comes back at 15, and typing an `X` at offset 4 of an existing draft leaves the caret at
5.

The panel does not jump, which is the hazard a taller composer creates. Traced per animation frame
at 900x900: into a chat with no draft the top edge eases 108 to 273.19 over 18 frames, largest step
25.56px; into a chat holding a draft at the field's maximum height (148px against 48), 108 to 174
over 12 frames, largest step 14.25px, with zero direction reversals in either. At 640x720 the laden
swap does not move the panel at all. The field reads 148 in the first traced frame and every frame
after, because a parent's layout effect runs after its children's.

`ChatView` was split to make room (the hint strip is its own component) and `newChat` moved beside
the three other swap cases in `sessionState.ts`.

## History

- 2026-08-06: Opened by the focus rule above, as something that rule made visible rather than
  created.
- 2026-08-06: Closed the same day on the maintainer's answer. The entry's claim held at every path
  and not only the two it named. One correction to its own text: "caret at 15" is the end of `half a
  question`, so it recorded where the caret already was. Cold-start adoption could not be reproduced
  in the browser, because the build self-summons and adoption is guarded on `touched`; it is covered
  in the reducer instead.

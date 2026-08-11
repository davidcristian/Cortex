# The composer's draft belonging to no chat

**Status:** landed 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened 2026-08-06 by
the focus rule above. The field is never unmounted, which is what keeps a draft alive across a trip
to the console, and it keeps it across a chat swap too: measured at 900x900, "half a question"
typed into the fresh chat is still in the field, caret at 15, after `Ctrl+↓` loads another
conversation. That was always true and was easy not to notice while focus landed on `<body>`; now
the caret is put in that field by the swap itself, so the first thing a reader meets in the
conversation that arrived is a sentence they started somewhere else. The two shapes are a draft
per chat (kept in the reducer beside `messages`, restored on arrival, which is what the composer's
local `text` state would have to give up) or a draft cleared by a swap, which is cheaper and
throws away work the user did. It wants the user's answer before either. Nothing blocks it.
- **LANDED 2026-08-06 as the first of those two shapes, on the user's answer**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). A draft per chat, taken over
  clearing on swap, because a half-typed question is work and swapping away is not a decision to
  discard it. **The entry's claim held, and at more doors than it named.** Reproduced at 900x900
  at HEAD: `{"value":"half a question","caret":15}` came through `Ctrl+↓`, a switcher row,
  `Ctrl+N`, the header's pencil, a delete confirm on the open chat and a reminder card's open
  control, every one of them, with the arriving chat's title in the header. One correction to its
  own text: **"caret at 15" is the end of the draft**, `"half a question"` being fifteen
  characters, so it recorded where the caret already was rather than a caret held mid-sentence
  (one parked at offset 2 also survived, as it happens). And cold-start adoption could not be
  reproduced in the browser at all: the build self-summons, `open` sets `touched`, and adoption is
  guarded on it, so the attempt is refused before a field exists to type into. It is covered in
  the reducer instead.
  **`OverlayState.drafts` keys the unsent text by session id and the composer is a controlled
  field over the entry for the chat on screen** (`overlay/drafts.ts`), so the arriving conversation
  is handed its own text in the commit that swaps the transcript: no arm parks anything, no effect
  runs in between, and no frame can paint the wrong conversation's sentence. **In the body's
  reducer rather than behind a store port**, argued in the addendum: the hard rule is about model
  processes and KV caches, which this is nowhere near, and the separate thing a store buys is
  survival of a body restart, which unsent text with no reader and no promise attached does not
  earn. In the reducer rather than in the component because the delete cascade has to reach it and
  a swap has to be synchronous, which also leaves a store one hydrate away if it is ever wanted.
  An empty field stores nothing, which is the whole eviction policy; a send spends the draft it
  sent and an example chip leaves it alone; typing sets `touched`, making that flag's own
  documentation true for the first time.
  **The caret lands at the end of a restored draft**, which is where the next character goes and is
  the field's own answer to having its value assigned. Measured at both viewports: a draft left at
  offset 2 comes back at 15, and typing an `X` at offset 4 of a standing draft leaves the caret at
  5 rather than at the end.
  **And the panel does not jump**, which is the hazard a taller composer carries. The swap alone,
  traced per animation frame with the switcher already open and settled. At 900x900, into a chat
  with no draft the top edge eases 108 to 273.19 over 18 frames, largest step 25.56px; into the
  chat holding a draft at the field's ceiling (a 148px pill against 48), 108 to 174 over 12 frames,
  largest step 14.25px, **zero direction reversals in either**, a jump-and-come-back being a
  reversal. At 640x720 the laden swap moves the panel not at all, one frame at 86, the panel
  already being at its ceiling. The pill reads 148 in the first traced frame and every frame after,
  never 48 and then 148: a parent's layout effect runs after its children's, so the composer has
  sized itself before the panel places itself in the same commit. `ChatView` was split to make room
  (the hint strip is its own component) and `newChat` moved beside the three other swap arms in
  `sessionState.ts`, both by responsibility rather than by line count.

## Trail

- 2026-08-06: Opened by the focus rule above, as a thing that rule made visible rather than made,
  and it was then the only entry anywhere whose blocker was a decision rather than work.
- 2026-08-06: Landed the same day on the user's answer, and the count of entries waiting on a
  decision rather than on work went to zero, where it had never been. The entry's claim held at
  every door and not only the two it named, which is worth recording in a backlog whose standing
  warning is that entries go stale. Nothing opened behind it.

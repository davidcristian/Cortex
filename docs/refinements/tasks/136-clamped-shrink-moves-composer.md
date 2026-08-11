# A shrink against the ceiling moves the composer

**Status:** satisfied 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

**Only the user can settle it.**
Two of the four fixes pull in opposite directions once the panel is tall enough
to be clamped: keeping the pinned edge unclamped is what makes the switcher's round trip exactly
reversible ([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 4), and it is also what pulls
the bottom edge back toward that pinned edge the moment a shrink gives it room, which is the one
thing the maintainer asked never to happen. Centring the summon (decision 8) took it from constant to
rare: measured at a 900px viewport, a correctly pinned panel has to grow 615px before the ceiling
binds at all, and acking a reminder, the pencil on a chat with a full reply in it, and a switcher
round trip now all move the composer 0px where they moved it 40, 13 and 3 before. A long
conversation still reaches the ceiling, and there it is a real choice, not a bug to be found: the
alternative design re-pins to the clamped edge on every content change (so the composer never
moves) and saves the pre-roll edge PER SECTION to hand back when that section rolls shut (so the
switcher's round trip stays reversible), at the cost of a panel that keeps whatever low edge its
tallest moment left it with until the next summon or view change. The user has been shown both;
this waits on which they want. Measured 2026-07-20. **Put to the user again 2026-08-04 and
deliberately left unpicked**, both designs restated with the rarity measurement above: the answer
was to spend the sitting on the entries that need no preference, so this stays open on a
preference rather than on work. That is a third outcome worth naming, since the entry had read as
though it were merely unasked, and the rarity is what makes waiting cheap.
- **CLOSED 2026-08-06 as MOOT, and there was never anything to pick**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). HEAD delivers BOTH designs at
  once, so the opposition the entry is built on does not exist and the user is owed no decision.
  The premise died thirty two minutes after it was filed, on the evening it was written: the
  entry landed in the console-and-motion commit at 20:25 on 2026-07-20, and four commits later at
  20:57 the panel's second bound was deleted. The clamp moved off the EDGE and onto the HEIGHT.
  `clamped(pinned, viewport, height)`, which was `max(0, min(pinned, 0.88v - h))` and is the whole
  mechanism this entry describes, became `clamped(pinned) = max(0, pinned)`, a no-op for any chat
  pinned at a positive edge, and `maxHeight(viewport, bottom)` caps the height instead. Nothing
  pulls the bottom edge any more: at the ceiling the panel stops getting taller and the history
  scrolls.
- **What was measured.** Driven by hand in headless Chromium against the demo bridge at 640x720,
  where the three reminders on the empty chat put the panel against its ceiling on arrival:
  `offsetHeight` 450 equals its `max-height` of 450 equals the `--ceiling` the panel publishes for
  itself equals `round(0.88 x 720 - 184)`, top edge 86, bottom
  edge 184px, and the composer's own bounding box top at 445 in viewport coordinates. Every
  number below is that composer box read per painted frame, not inferred from the panel's edge.
  Acking one reminder gives back 58px of real content (the stack measures 188 then 130, and the
  history's box grows 99 to 158 taking the room up): the panel holds 450 tall at a 184px edge on
  all 75 frames and **the composer reads 445 on every one of them, travel 0px**. A switcher round
  trip while clamped opens a 135px list inside the panel and rolls the stack to 100, then hands
  both back at 0 and 188; the panel reads 450 at 184px before, during and after, and the composer
  445 throughout, so **the round trip is exactly reversible AND the composer never moves**, which
  is the pair the entry says cannot be had together. Acking all three, which takes the panel clean
  off its ceiling, moves the TOP edge 86 to 184 and the height 450 to 352 with the bottom edge at
  536 and the composer at 445 on every frame: the shrink is taken entirely at the top. Repeated at
  900x900, where the panel also arrives clamped (518 tall at a 274px edge): the ack drops the top
  edge 108 to 138.5 with the composer at 535 on all 76 frames, and the switcher round trip returns
  the panel to the identical 274px edge with the composer at 535 throughout.
- **The measurement was proved able to fail before it was trusted.** Restoring the deleted clamp
  at the one line that spends it, `edge = max(0, min(wanted, 0.88v - height))`, which is the old
  `clamped` verbatim, and re-running the same scenario: the panel arrives 546 tall at an 88px edge
  with the composer at 541, and acking one reminder settles it at 483. That is the 58px the entry
  describes, through a 96px excursion (541 down to 445 across the roll, back up to 483), and the
  edge walks 88 to 184 to 146. The change was reverted immediately and every green number above
  was re-taken afterwards and reproduced.
- **Why it stood for seventeen days**, which is the part worth keeping. Nobody re-derived the
  entry after the same evening's fix, and two later sittings measured the answer and read it as a
  null result. The panel-watch sitting recorded on 2026-08-03 that "the composer holds its bottom
  edge at 493 through an ack and a switcher round trip either way", and the chat-floor sitting the
  same day that the composer held "still through an ack, a switcher round trip and the pencil at
  both viewports". 493 is this panel's composer bottom at 640x720 exactly, and both readings are
  the closure above. Each concluded only that the undecided preference was "not settled here by
  accident", which was true of those changes and was also the answer to an entry sitting in the
  same file. An entry restated from its own text rather than from the code will survive any number
  of measurements taken alongside it.
- **The rarity number it was restated with is wrong, and wrongly reassuring.** "A correctly pinned
  panel has to grow 615px at a 900px viewport before the ceiling binds at all" reads 615 as a
  growth delta when it is the CEILING'S VALUE for a 546px panel centred at 900px. Headroom is
  `ceiling - h`, and for a centred panel that is `0.88v - (v - h)/2 - h`, which at 900px is
  `342 - h/2`: 69px for that 546px panel, at most 342px for any panel at all, and 0 at
  `openHeight(900) = 684`. Measured live at 900px, the demo's own arriving chat has 0px of
  headroom and is against its ceiling before the user has touched anything. The ceiling is not
  rare, and it never was; what is gone is the composer moving when the panel meets it.

## Trail

- 2026-07-20: Measured at a 900px viewport and filed with both designs put to the user.
- 2026-08-03: Two sittings in this area measured the closure and recorded it as a null result, the
  panel-watch sitting reading the composer's bottom edge at 493 through an ack and a switcher round
  trip either way and the chat-floor sitting reading it still at both viewports. Each was asking
  whether its own change had moved the composer rather than whether anything still did.
- 2026-08-04: Restated from its own text and put to the user again, deliberately left unpicked,
  which the sitting recorded as a third outcome.
- 2026-08-06: Closed as moot with no code written and nothing for the user to pick. The mechanism it
  argues about was deleted thirty two minutes after the entry was written, the clamp moving off the
  pinned edge and onto the height, and the reading was reddened first by restoring the deleted
  clamp. The area went 13 to 12, and this closed the last entry here whose blocker was a preference
  rather than work. It was also a closing species this backlog had not held before: entries here had
  been wrong about a cause, a size, a fix and a cost, and this one was wrong about whether its
  subject was still in the tree.

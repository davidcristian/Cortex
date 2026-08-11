# A section in the panel's chrome shrinking the log

**Status:** landed 2026-08-04
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

The switcher list and the reminder stack roll outside the history, so at the panel's ceiling their
growth comes out of the history's window rather than out of the panel, and the ride above never
hears them: it is subscribed to the box, and their start event goes to the panel instead. Measured
2026-08-03 at 640x720 on a full history: opening the chat switcher takes the history's window 293px
to 73px with `scrollTop` left at 408, so the reader's distance from the end of the reply goes 3px
to 223px in one roll, and closing it reads 3px again. The same arithmetic answers it, the ride
being written against a box and a section rather than against the history; what it needs is to
hear a roll that happens outside the box, which means the panel dispatching to it, and its own
measurements across the summon, a new chat and a reminder ack, where the panel is moving on its own
account (an arrival centres it, an interrupted ease is carried, and the ride-along is already
driving the bottom edge). Deferred because it is exactly reversible, the reader can scroll, and
the three panel motions it would have to be measured against are each their own sitting.
- **LANDED 2026-08-04 on the ride it named, and "the same arithmetic answers it" was the one
  thing it got wrong** ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). The setup and
  the diagnosis reproduce exactly, on a full history at 640x720 with the panel on its 450px
  ceiling: the window runs 293px to 73px, the reader's distance from the end of the reply 3px to
  223px, and listeners on the history, its column and the panel say who hears the roll, which is
  the last two and never the box. Everything after that sentence cost more than the entry thought.
  **Wired up with the arithmetic untouched, the ride hears the roll and does nothing at all**: the
  cap that keeps a rolling section's own top edge on screen is expressed as the room between that
  edge and the box's top, and a section in the chrome is ABOVE the box for every frame, so the
  floor that stops the ride chasing a section already off the top turns that room into none and
  freezes the ride where it started. Measured in that state, `scrollTop` read 173 on every frame
  of the roll, byte for byte the trace with nothing listening. The rule that answers it is one
  line, `box.contains(section)`, and it says what the cap was always about: only a section inside
  the box is something the reader can be carried away from, a switcher list staying where the
  panel put it whatever the log does underneath. **The pair the entry named is one section and a
  family.** The reminder stack is gated on an empty log, the same gate the entry above was caught
  on, so it can never cost a reader anything: acking one of three grows the history 99px to 158px
  with 99px of content, and `scrollTop` and the tail read 0 on all 21 painted frames. What it did
  not name is the family that does reach the log, since every row inside those two lists rolls
  through the same component, and a row deleted from the open switcher moves the log exactly as
  the list does (window 170px to 220px, `scrollTop` 299 to 249, tail 0 throughout). The
  subscription moves from the box to the column the panel renders the view into, and the rolling
  element is read off the event's target rather than searched for, which keeps two rolls in one
  frame apart. After, per painted frame: the tail reads 3px on all 19 frames of the switcher's
  roll open and all 19 of its roll shut, `scrollTop` running 173 to 393 and back to the pixel it
  started from, no frame moving it more than 34px, inside the roll's own 300ms. The three panel
  motions the entry wanted measured are each clean: a switcher opened 100ms into a summon holds
  the tail at 0 for every frame while the panel's top edge travels 129.76 to 85.54 and the window
  390px to 170px; `Ctrl+N` on a full history with the list open empties the log, so there is
  nothing to hold and the panel eases 86.5 to 145.5 undisturbed; and the ack is the no-op above. A
  reader who has scrolled up is still left alone, `scrollTop` reading 40 on every frame of a
  switcher closing under them. One measuring lesson came out of it: read in a
  `requestAnimationFrame` the ride looks one frame behind (a 36px peak on the way open), because
  those callbacks run before the ride's own; the `ResizeObserver` step runs after all of them, so
  that is where the frame the browser actually paints can be read.

## Trail

- 2026-08-03: Opened when the tail-pin ride landed, being the same defect from the other side, where
  the ride never hears a roll that happens outside the box.
- 2026-08-04: Closed on that same ride. The setup and the diagnosis reproduced exactly and the
  sentence that sized the work did not, wiring the ride up with its arithmetic untouched having
  changed nothing at all, and the pair the entry named turned out to be one section and a family.

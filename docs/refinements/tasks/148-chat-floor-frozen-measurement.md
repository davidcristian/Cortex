# The chat floor's frozen measurement of the empty state

**Status:** landed 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md), the chat's floor under the empty state ([overlay-ux.md §3](../../design/overlay-ux.md))

The panel no longer shrinks when the first message is sent, because `.log` carries a `min-height` of
185px: the empty state's own height, measured in Chromium at 640x720 and at 900x900, where it
comes out the same because none of it is viewport-height-derived (32px of padding, a 54px mark,
13px, a 16px line, 13px, a 31px row of chips, 26px). That is a measurement frozen into CSS. Change
the mark's size, the invitation's font, or the number of example chips and the two drift: too low
and the panel dips again by the difference, too high and the empty state gains that much dead
space around the chips, split above and below by its `margin: auto`. Neither is dangerous at the few-px
scale, and the CSS comment carries the arithmetic so the check is possible by hand; what is
missing is that anything does it. Viewport *width* used to be one input the number had without stating it,
since `.empty-chips` was `flex-wrap: wrap`: measured across widths, the two chips sat on one row
at 580px and above (185px) and took a second row at 560px and below (224px), so a first send in a
560px window cost the panel 39px. **That half was closed on 2026-07-20**, not because the window
became reachable but because a finer sweep showed the margin was thin: the labels wrap at a 526px
panel and the shipping 640px window gives them a 560px one, so the clearance is 32px of label
width, which the same string in Segoe UI could consume. The chips are now held to one row and shrink
to an ellipsis rather than wrapping (`.empty-chips`, `flex-wrap: nowrap` with the caps that make
the shrinking reach them), measured at 185px at every width from 700px down to 440px with no
horizontal overflow, so the number no longer depends on width in any engine. The engine is still
the same question asked once about the rest: 185px was measured on Chromium under Linux, and the body renders on WebView2 with
Segoe UI, where the invitation's line box and the chips' height are the parts that could come out
a pixel or two different. Same few-px consequence, and the same fix retires it. The version that
cannot drift measures the rendered empty state once at startup and publishes it as a custom
property the floor reads, which is the same probe the reserved rail's assumed width wants
(above), and a shared one would answer both. It stays
deferred because a CSS-only fix bought the whole behaviour, and a module plus its tests is a
larger thing than the defect it would prevent. A structural test (`Panel.test.tsx`, "keeps the
invitation and the bubbles that replace it in the same floored column") pins the other half: the
floor only works while the empty state and the bubbles share the column it is on, which no
stylesheet can defend.
- **LANDED 2026-08-03 as the published property this entry asked for, `--chat-floor` from
  `overlay/measured.ts`, and the entry was describing a constant that had not existed for
  fourteen days** ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). `.log`'s
  `min-height` was deleted on 2026-07-20 by the settings-tab slice, about forty minutes after this
  text was written, on the reasoning that the reminder stack now rolls away on the first message
  so the shrink is deliberate. That is true of a chat with reminders due and false of every other
  chat, and nothing re-read the entry, so this backlog carried a note about tuning a number that
  had been removed while the defect it prevented was live underneath it. **What that cost,
  measured at 60Hz over the demo with the stack acked, at 900x900 and 640x720 alike: the first
  message took the panel 352px to 262px and back to 297px as the reply began.** The composer's own
  top edge reads 535 (and 445) for every frame of it, the panel being pinned below, so the whole
  90px is the conversation dropping and climbing back. This entry predicted "a few pixels of dip";
  it was 90, and by deletion rather than by drift.
  **The other two frozen numbers were audited before anything was built, and neither had drifted.**
  `--trace-row` is still exactly the chip's box (the live chip's laid-out height is 24.000px and
  the settled disclosure's own is 20px, floored to 24 by the token), and `--rail` is still what
  Chromium reserves (6px on both unbordered scroll boxes, `.history` and `.field`). The trace row
  is retired here: `.chip`'s own floor was a no-op restating its natural height back at itself, so
  it is gone and the chip publishes its box for the disclosure to floor on. The rail is not, and
  the entry below says why.
  **The design differs from this entry's guess in the one way that matters: a startup probe cannot
  do it.** There is no empty state and no chip at startup, so a startup probe would have to render
  a hidden copy, which is this exact defect one layer down with nobody looking at the copy. Both
  elements are instead already in the tree exactly when their number is knowable and leave exactly
  when it starts to matter, so the probe measures the real one, and the empty state's is a
  reading plus a `ResizeObserver` rather than a single reading: measured at boot, it is 183px in
  the frame React attaches it and 185px two frames later, the example chips' row coming out 29px
  before the system font stack resolves and 31px after. A chip gets one reading, being unable to
  appear before the user has typed and able to appear twice at once, which one watch could not
  hold honestly. The engine half of this entry is therefore
  answered rather than deferred, the number now being measured on whatever engine is running.
  **The removal's own reason was real and is answered separately.** A column taller than the box
  it scrolls in overflows, so with the stack still rolling away a thumb appears for 8 frames
  (the removal reported seven). The rule that hides the history's thumb while the panel is
  `[data-resizing]` now covers the stack's roll as well, naming the aside rather than any rolling
  section: the general version hid a thumb that was already on screen for 38 frames of one
  switcher round trip over a history scrolling 845px inside 293px, to save 8 frames that should
  never have had one.
  **The demonstration is the whole point of the entry.** Lengthening the invitation by one wrapped
  line takes the empty state to 201px: the measured floor follows and the panel stands at 368px
  both before the send and after it, where the same edit under a frozen 185px leaves 368px before
  and 352px after, which is 16px of exactly the drift this entry described. The invitation was put
  back.

## Trail

- 2026-07-20: Measured in Chromium at 640x720 and at 900x900 and filed, with the width half of the
  number closed the same day by holding the example chips to one row.
- 2026-08-03: Landed as `--chat-floor` from `overlay/measured.ts`, over a defect it did not know it
  had: `.log`'s `min-height` had been deleted about forty minutes after the entry was written, so
  the first message took the panel 352px to 262px and back to 297px, which is 90px rather than the
  few pixels of dip the entry predicted, and by deletion rather than by drift. The other two frozen
  numbers were audited and neither had drifted; `--trace-row` was retired with it and the rail was
  not. A startup probe could not have done it, so the real elements are measured as React attaches
  them. The index read this close as the sharpest instance yet of its standing warning about an
  entry's own text, and sharpened that warning on it: the lesson is about staleness rather than cost
  estimates: an entry describing a line of code is stale the moment that line moves and nothing in
  the process re-reads one.

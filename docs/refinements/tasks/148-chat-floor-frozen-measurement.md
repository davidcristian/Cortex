# The chat floor's frozen measurement of the empty state

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md), the chat's floor under the empty state ([overlay-ux.md §3](../../design/overlay-ux.md))

The panel stopped shrinking when the first message was sent because `.log` had a `min-height` of
185px: the empty state's own height, measured in Chromium at 640x720 and at 900x900, where it
comes out the same because none of it derives from viewport height (32px of padding, a 54px mark,
13px, a 16px line, 13px, a 31px row of chips, 26px). That is a measurement written into CSS, so
changing the mark's size, the invitation's font or the number of example chips makes the two
disagree.

Viewport width used to be an input the number had without stating it, since `.empty-chips` was
`flex-wrap: wrap`: the two chips sat on one row at 580px and above (185px) and took a second row
at 560px and below (224px), so a first send in a 560px window cost the panel 39px. That half
closed on 2026-07-20, not because the narrow window became reachable but because the margin was
thin: the labels wrap at a 526px panel and the shipping 640px window gives them a 560px one, so
the clearance is 32px of label width, which the same string in Segoe UI could consume. The chips
are now held to one row and shrink to an ellipsis rather than wrapping, measured at 185px at every
width from 700px down to 440px with no horizontal overflow.

**Shipped 2026-08-03 as `--chat-floor` from `overlay/measured.ts`, and the entry was describing a
constant that had not existed for fourteen days**
([ADR-0035](../../adr/ADR-0035-console-and-motion.md)). `.log`'s `min-height` was deleted on
2026-07-20 by the settings-tab slice, about forty minutes after this text was written, on the
reasoning that the reminder stack now rolls away on the first message so the shrink is
deliberate. That is true of a chat with reminders due and false of every other chat. Measured at
60Hz over the demo with the stack acked, at 900x900 and 640x720 alike, the first message took the
panel 352px to 262px and back to 297px as the reply began. The composer's own top edge reads 535
(and 445) for every frame of it, the panel being held below, so the whole 90px is the
conversation dropping and climbing back. The entry predicted a few pixels; it was 90, and by
deletion rather than by divergence.

The other two frozen numbers were checked before anything was built and neither had moved.
`--trace-row` was still exactly the chip's box (the live chip's laid-out height is 24.000px and
the settled disclosure's own is 20px, floored to 24 by the token), and `--rail` was still what
Chromium reserves (6px on both unbordered scroll boxes, `.history` and `.field`). The trace row
was retired here, `.chip`'s own floor having been a no-op restating its natural height, so the
chip now publishes its box for the disclosure to floor on. The rail is not, and
[R-146](146-reserved-rail-assumed-width.md) says why.

A startup probe cannot do this, which is where the design differs from the entry's guess: there is
no empty state and no chip at startup, so a startup probe would have to render a hidden copy,
which is the same defect one layer down. Both elements are instead already in the tree exactly
when their number is knowable and leave when it starts to matter. The empty state's is a reading
plus a `ResizeObserver` rather than a single reading: measured at boot it is 183px in the frame
React attaches it and 185px two frames later, the example chips' row coming out 29px before the
system font stack resolves and 31px after. A chip gets one reading, being unable to appear before
the user has typed and able to appear twice at once. The engine question is answered rather than
deferred, the number now being measured on whatever engine is running.

The deletion's own reason was real and is answered separately. A column taller than the box it
scrolls in overflows, so with the stack still rolling away a thumb appears for 8 frames (the
deletion reported seven). The rule that hides the history's thumb while the panel is
`[data-resizing]` now covers the stack's roll as well, naming the aside rather than any rolling
section: the general version hid a thumb that was already on screen for 38 frames of one switcher
round trip over a history scrolling 845px inside 293px, to save 8 frames that should never have
had one.

The demonstration is the point. Lengthening the invitation by one wrapped line takes the empty
state to 201px: the measured floor follows and the panel stands at 368px both before the send and
after it, where the same edit under a frozen 185px leaves 368px before and 352px after, which is
16px of exactly the divergence this entry described. The invitation was put back.

A structural test (`Panel.test.tsx`, "keeps the invitation and the bubbles that replace it in the
same floored column") covers the other half: the floor only works while the empty state and the
bubbles share the column it is on, which no stylesheet can defend.

## History

- 2026-07-20: Measured in Chromium at 640x720 and at 900x900 and filed, with the width half closed
  the same day by holding the example chips to one row.
- 2026-08-03: Shipped as `--chat-floor` from `overlay/measured.ts`, over a defect it did not know
  it had. The index read this close as the sharpest instance yet of its warning about an entry's
  own text, and sharpened that warning on it: an entry describing a line of code is stale the
  moment that line moves, and nothing in the process re-reads one.

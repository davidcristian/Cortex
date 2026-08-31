# Readings: the overlay panel's motion

The traces the panel's geometry rules rest on. Cited by
[ADR-0035](../adr/ADR-0035-console-and-motion.md), decisions 7, 8, 11, 12, 32, 33 and 34, and by
[ADR-0037](../adr/ADR-0037-whisper-streaming.md), decisions 10 and 11. Every reading is geometry in
a browser at a stated viewport, so it depends on the viewport and the font stack rather than on the
machine's speed; the durations are the animations' own schedule.

**Method, for all of them:** headless Chromium driving the real overlay over the demo bridge
(`bridge/demoBridge.ts`), sampling every painted frame (from a `ResizeObserver` registered after
the panel's own where a frame's placement matters, since `requestAnimationFrame` runs before it),
with `Element.prototype.animate` instrumented where animation counts are given. The body's own
window is 640x720. The traces behind individual lines of the motion code, rather than behind a
decision, are in [overlay motion traces](overlay-motion-traces.md).

## Pacing and resuming a move (decisions 7 and 11)

**2026-07-20**, one streamed reply at 900x900, sampling each frame for how much of the history the
panel had not yet grown to fit:

| variant | mean lag | peak lag | frames with the text fully visible |
| --- | --- | --- | --- |
| every move forced to a flat 380ms | 13.8px | 70px | 354 of 661 |
| paced by distance | 1.2px | 35px | 573 of 661 |

With resuming added (same reply): 14 panel animations instead of 26; a 23px line of growth arrives
120ms after it appeared however many tokens retarget it; the panel stops moving 133ms after the last
word instead of 285ms.

## The arrival window (decision 8)

**2026-07-20**, 900px viewport, where a true centre puts the panel's bottom edge at 722.9. A
switcher round trip started 100, 300, 450, 600 or 1500ms after the panel appeared settles at 723 to
725; without the touch ending the window, the first two settled at 730 and 783. Acking a reminder,
the pencil on a chat with a full reply, and a switcher round trip move the composer 0px, against
40px, 13px and 3px when the summon fixed the panel at the height it had while shut.

## The chat floor (decisions 12 and 35)

**2026-08-03**, empty chat, reminder stack acked, first message sent, at 640x720 and 900x900 alike:

| floor | panel height across the send |
| --- | --- |
| none (the floor deleted) | 352px, dipping to 262px, then 297px as the reply began |
| measured `--chat-floor` | 352px on every frame until the reply grows it |

The published floor reads 183px in the frame the empty state attaches and 185px once the font
stack resolves; the chip publishes 24px. With the invitation lengthened by one wrapped line (201px)
the measured floor keeps the panel at 368px across the send, where a floor frozen at 185px dips it
to 352px.

## The box watch (decision 32)

**2026-08-06**, 900x1000, empty chat: 150px appended to the log and 40px more 100ms into the
resulting ease. Waiting the ease out, the second growth was invisible from t=160 to t=333 and the
panel settled at t=465; with the probe it is answered one frame later and settles at t=339.
Letting every notification place instead ran 24 animations for one 150px growth, against 2.

## Sub-pixel heights (decision 33)

**2026-08-06**, 900x1000, one streamed reply: 310 of 330 `offsetHeight` reads of the panel dropped a
fraction (worst 0.484px) and a retarget stepped the painted top edge back 0.281px. Reading the used
height, the worst backward step is 0.015px, Chromium's 1/64px grid. A section's roll that measured
with `offsetHeight` ended 0.25px from its target (193.75px against 194px); with the used height the
step at every roll boundary is 0.000px. **2026-08-07**: the whisper bubble's published target was
half a pixel under its own box on every wrapped line (45 against 45.5); publishing `toFixed(1)`
closes it.

## The height budget (decision 34)

**2026-08-03**, 640x720, twelve chats and eleven reminders so both sections reach their caps. The
distance of each box past the panel's clipped edge (negative is inside):

| state | hint strip, `vh` caps | budgeted | composer, `vh` caps | budgeted |
| --- | --- | --- | --- | --- |
| reminder stack alone | -1 | -1 | -43 | -43 |
| switcher alone | 24 | -1 | -18 | -43 |
| both sections | 246 | -1 | 204 | -43 |
| both, draft at the field's ceiling | 282 | -1 | 240 | -43 |

At 640x1400, 640x1000 and 640x900 with both open the hint strip reads -1 where it read 450, 322
and 290. **2026-08-08**: capping the roll's wrapper rather than the card moved the shortest viewport
where everything fits from 286px to 220px (level at 218px), with the body's 640x720 bit-identical.
Easing the shares on the roll's clock: acking the last reminder with the switcher open used to step
the switcher 135.14px to 241px in one frame; it now covers the same travel over 19 frames, largest
single frame 15.94px, and the history's worst frame goes from 105.86px to 4.31px.

## The whisper bubble

Cited by [ADR-0037](../adr/ADR-0037-whisper-streaming.md).

**2026-07-21**, frame cost (the one reading here that depends on the machine's speed), 660x760,
every frame of one whole demo stream (breath, a reasoning burst, condensation, drain): 540 frames,
every one at the 60 Hz refresh interval (median 16.7ms, worst 16.8ms), the answer the mark's own
clock gave.

**2026-07-21**, joining the roll contract (decision 10), 660x1000, one reply grown past the chat
floor: before, the panel's top edge snapped backwards eight times, by up to 6.6px; after, zero
reversals and zero backward snaps.

**2026-08-18**, the re-lay on resize (decision 11), one demo reply at 900x1000, where the log is
526px wide and the letters lay at a 431px wrap over two lines. `.panel` is `min(560px, 92vw)`, so
the panel is 560px wide at every viewport over about 609px, and readings at 900, 1400 and 640 change
nothing. Resized to 480 mid-stream, the letters re-lay at a 334px wrap and the reply settles over
six lines; widened back to 900 the settled bubble re-poses from 364x157.5 to 461x135.5, and narrowed
to 420 it settles at 318x180.5, its painted edge inside the log at every reading. With `watchWrap`'s
listener prevented from attaching, the 431px wrap holds throughout and the bubble stands 53px past
the log's right edge at 480 and 109px past it at 420.

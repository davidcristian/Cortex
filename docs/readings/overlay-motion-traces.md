# Readings: traces behind the overlay's motion code

The frame by frame traces the overlay's panel, composer and rolling sections were written from.
[panel motion](panel-motion.md) has the readings that
[ADR-0035](../adr/ADR-0035-console-and-motion.md) and
[ADR-0037](../adr/ADR-0037-whisper-streaming.md) cite by decision. This record has the rest: the
traces that explain why a particular line of `body/app/src/overlay/` or `body/app/src/components/`
is written the way it is.

**Method, for all of them:** headless Chromium driving the real overlay over the demo bridge
(`bridge/demoBridge.ts`) at the stated viewport, sampling every painted frame. "At 60Hz" means one
sample per painted frame on a 60 Hz display. Each reading is geometry in a browser, so it depends on
the viewport and the font stack rather than on the machine's speed. The body's own window is
640x720. Only the two readings that state a date were dated when they were taken.

## Why the height is animated in code

A `transition: height` never fires on the panel, because its height is `auto` on both sides and only
the content changed, which is not a change of computed value. `interpolate-size: allow-keywords`
does not help: it makes `auto` interpolable against a length, not one content-driven `auto` against
the next. Measured in a browser with the transition declared and `interpolate-size` set, opening the
chat switcher moved the panel through exactly one distinct height.

With one fixed duration for every move, the content grew in 22px steps and the panel's top edge
stayed about 6px per 200ms behind it, a whole line of text behind for the length of the reply. A
token arrives about every 55ms, each one re-renders the panel, and each render restarted the 380ms
ease.

Pacing the duration by distance is not enough on its own. With the 120ms minimum in place but before
a render could continue a move it had not redirected, a 23px line of growth started four eases,
120ms each and 55ms apart, and settled 285ms after the text appeared.

The longest move the panel makes is a full-height chat to the console. At a 900px viewport that
slides the top edge 243px, from `12vh` above a 684px panel to the centre of a 198px one.
`FULL_TRAVEL_PX` is rounded down to 240 so that move gets the whole 380ms and every taller viewport
does too.

## The ceiling and the bottom edge

**A second bound on growth.** Until it was removed on **2026-07-20** the panel had a flat maximum
height as well as the `12vh` of clear space, so a panel already at the clear space kept growing
downward to reach it, walking its bottom edge down the screen with the composer on it. Acking one
reminder then moved the composer 40px up the screen. (Re-measured on 2026-08-06, that shrink moves
the composer 0px; see [panel motion](panel-motion.md).)

**A prediction above the ceiling.** At 60Hz, opening the chat switcher on a full-height panel ran
the panel's bottom edge 108px down to the floor of the screen over the roll and then brought it
back: the arithmetic had been asked where an 874px panel goes in a viewport that allows 684.

**Moving after the roll instead of along it.** At 60Hz, opening the switcher on a panel already at
its ceiling ran the top edge 12px off the top of the screen and then slid the whole panel back down,
and closing it dipped the top edge 120px and brought it back up. Moving the bottom edge over the
same roll keeps the top edge still through both.

**Cancelling an interrupted ease.** Handing the used height straight back to layout, rather than
continuing the interrupted ease over the roll's own clock, dropped the top edge 61px in one frame
with nothing animating it.

**Composing a residual onto `auto`.** Measured in Chrome, an additive `height` animation over an
`auto` height is demoted to replacing it, and the panel then does not follow the roll at all.

**The measuring cap left on for the length of a roll.** At 60Hz at 640x720 with the panel near its
ceiling, opening the chat switcher rolled the panel to the loose 547px with its top edge off the
screen, and the placement at the end of the roll put the real 351px back in one frame.

**Measuring a panel under that loose cap after a roll.** A panel at its 450px ceiling with the
switcher open reads 547px under the loose cap, and easing from 547 to 450 is a 97px jump to a top
edge 11px off the screen, followed by a slide back down.

**The ceiling in the keyframes.** At 60Hz at 640x720, opening the console from a full-height chat:
with the destination's cap applied to the element rather than written into both keyframes, the ease
was written 450 to 347 and the panel stood at 351 one frame after the click, easing the last 4px
from there. The reader sees the whole shrink in one frame and then an animation of nothing.

**Sizing the cap from the previous edge.** That lags a render: at 900px the empty chat settled 82px
below centre and scrolled, having capped itself at 520px where 604px would have fitted.

**A fractional ceiling.** Left fractional, `maxHeight` was rounded by `panelPlacement` on the way to
`max-height` while `slideWithRoll` capped its prediction at the raw value, 0.2px apart. That is under
`MIN_DELTA_PX`, so nothing animated it, but the bottom edge is written rounded and 0.2px is enough
to cross a rounding boundary. At 60Hz at 640x720 with the reminder stack up, so the panel sat at its
ceiling, every roll of a section inside it began with `bottom` stepping 87 to 86 in one frame with
nothing easing it, and stepping back the frame the roll ended.

**A rounded bottom edge.** At 901x1001, one growth's whole ease painted a 324.5px edge and the frame
that took the animation away handed back the 325px inline value: half a pixel of the panel's
bordered, shadowed edge stepping with nothing moving it.

**The edge a view of more than one shape arrives on.** Adding the slack to the edge and letting the
panel's own rule about which edge stays still correct it on the next render put the console through
two eases, the second sliding its bottom down 44px after it had apparently arrived.

## The summon's arrival window

At 60Hz, the summon's reminder stack rolls open 10ms behind the summon and settles 340ms later.
Counting that as growth rather than as part of the arrival fixed the panel to the centre of the
356px it had before the reminders arrived, and it spent the rest of the session 109px above its own
centre and hard against its ceiling.

At 60Hz in a 900px viewport, opening the chat switcher 410ms after the summon wrote an edge of 117px
for the 666px the panel would be with the list open. Closing the list left the 546px panel on that
same 117px, 60px below its own centre, where it stayed for the rest of the session, because nothing
clears that edge afterwards: a trip to the console and back stores it and hands it straight back.

At 900x1000, Ctrl+N with the switcher list open, so the list rolls shut behind the summon while the
reminder stack is still there: counting the centring by asking only whether the rolling section was
the aside, instead of counting it through `centringHeight`, fixed the panel at 227 where the
placement at the end of the roll re-centred it to 324, and a touch inside the arrival window, which
is what stops that placement re-centring, left the session 97px low for the rest of it.

Bounding that same prediction at the old edge's ceiling rather than at `openHeight`: at 760px with
the demo's reminders it cost the history 119px over the roll and gave 40px back in a second ease.

At 60Hz at 640x720 with a conversation and the session list up, writing the next edge while the
panel is closing arrives in the frame of the dismiss, with the panel still full size and fully
opaque: it went from 450 tall at a 184px edge to 508 tall at a 106px edge in one frame, and only
then began to shrink away.

## Reading the panel's own box

At boot, `getBoundingClientRect` read the panel 327.5px tall against a layout height of 356, because
the panel is scaled through the whole summon. Every geometry taken during a summon was about 8%
short, the edge the session ends up on included.

Measured in Chromium on a 356.281px box with a 1px border: `offsetHeight` reads 356 whether or not
the box is scaled, the rect reads 356.266 plain and 327.764 under `scale(0.92)`, and the used height
off the computed style reads 356.266 under both. The used height also follows a running height
animation, so it is safe to read mid-move: an element easing 400 to 500 reports the in-flight
409.984, and its natural height again once that animation is cancelled.

Measured in Chromium at 900x1400, with 60px appended into the log and 40px more two frames into the
resulting ease: the box read 567.906 for both frames, while the same element read through an
`!important` inline `height: auto` read 616.75 and then 667.75, which is the growth arriving.
Nothing paints in between, and the read raises no resize notification of its own: instrumented over
the demo, the observer's "loop completed with undelivered notifications" error fired zero times.

## The panel's watch on its own box

At 900x900 with the demo's reminder stack opening, a section's roll raised 19 resize notifications
across the 300ms roll, and one of the panel's own 380ms moves raised 18 in the same trace.

Until **2026-08-06** the watch did nothing at all while a move of the panel's own was running, at a
measured cost of up to a whole move's length of latency.

At 640x720 with the reminder stack acked, a Shift+Enter that restacks the pill and adds a line runs
the panel through 184, 181.17, 168.08, 150.48, 140.5, 135.36, 132.88, 132.03, 132. Before the draft
moved into the reducer, the same keystroke was driven by the resize observer through 184, 181.14,
168.08, 150.41, 140.5, 135.34, 132.88, 132.03, 132.

Measured over a draft typed character by character, a restack, a paste to the field's ceiling, a
swap in and out of the chat holding it, and a send, at both viewports: zero loop errors and no
motion the placement in the same render had not already made.

Measured over the demo before the watch was dropped for the frame the panel writes in: one "loop
completed with undelivered notifications" error per keystroke that grew the pill.

At 640x720 over a Shift+Enter that restacks the pill, `requestAnimationFrame` runs before the resize
observer steps, so a trace taken there reads 404 for the frame the character arrived, while a probe
reading the same frame after the placement reads 352 with one animation attached.

## The scrollbar thumb during a resize

Mid-ease the panel is shorter than the height it is easing to, so the history overflows for a few
frames and shows a thumb for a size the panel never settles at. Clearing the resizing attribute from
`oncancel`, which arrives asynchronously and therefore after the replacement animation has already
set it, left 19 frames of a single reply with the history overflowing and the panel unmarked.

## The section roll

At boot, measuring the roll's target with `getBoundingClientRect` rolled the reminder stack to a
target 8% short of its content and snapped the last 16px on when the roll ended, because the panel
around it is scaled through a summon.

Measured over the demo at 900x1000, the reminder stack's aside is 193.75px tall and `offsetHeight`
rolled it to 194.

At 60Hz, a closing roll with the default `fill: "none"` snapped back to its natural height the
instant the animation ended and painted there until React caught up: one frame of the whole switcher
reappearing, which the panel measured too.

Under `prefers-reduced-motion`, with no animation running and no collapsed height written by hand,
closing the chat switcher left the panel 119px lower than it had been before it opened, and it
stayed there.

Measured in Chromium at a 900px viewport, which side of `element.animate` the start event falls on
changes nothing, because the section's current height cancels out of the panel's prediction: a
listener before `animate` reads 464 less 76 plus 76, one after it reads 388 less 0 plus 76, both
464, and the two 60Hz traces of the panel are frame for frame identical. The one real ordering
constraint is that the event follows the attribute that publishes the target height.

## Rows that travel

At 900x900 before `useTravel` existed, marking the third of three chats as `pinned` took it from 270
to 170 and pushed the two above it 50px each, all inside the single frame the re-listing committed.

A deleted row's neighbours travel 50px over its 300ms exit, and no commit happens while a roll runs,
so the commit at the end of the exit would read that travel as a 50px jump to correct, and send the
neighbours back down to cover it again.

## Where the caret goes

At 900x900 with the caret on a resting row's pencil, `Ctrl+K` kept the caret for the 300ms roll and
then read `<body>` at 353ms, which is outside the panel and one Tab from the top of the page.

Pressing the header's chats button moves the caret out of the row and onto the button at 45ms, so
the caret is already on the anchor by the time the close is decided.

`Ctrl+K` pressed from the composer leaves a half-typed draft alone, with its caret at offset 4 of
"half a question".

At 900x900, pressing an example chip sends its prompt and takes the whole empty state away, the
reminder stack above it included, and the caret read `<body>` at 39ms.

At 60Hz at 640x720 with the session list open, focusing the composer without `preventScroll` on the
return from the console sent `panel.scrollTop` from 0 to 139 in the frame focus arrived, unwinding
over the ease: the whole panel's contents slid 139px and crept back.

## The composer's pill

Traced character by character over two lines, the send button's rect was identical in all 183
samples across the switch from the inline layout to the stacked one.

Inline, the button is a flex sibling of the field and reserves its column down the whole pill, so
every wrapped line stopped 44px short of the right edge. A stacked field is that 44px wider, which
is why the layout is always decided at the inline width.

Traced in Chromium at the panel's 560px, a line of prose needs two lines inline and one stacked for
five or six characters, and where that band starts depends on the glyphs: 60 through 65 characters
on one traced line, 62 through 66 on another.

Traced from inside the measurement at 640x720 with a two-turn chat, dropping the stacked class
without keeping the pill's height: the pill read 100px on entry, 75px with the class off and 100px
on exit, and the scrolling log beside it read 144, 169 and 144. Chromium clamped the log's
`scrollTop` to 62, where 87 shows the newest reply, so every later keystroke walked that reply off
the bottom edge.

At 900x900, before the composer listened for a resize, a one-line draft measured at 34px stayed at
34px with `scrollHeight` at 50 after the viewport narrowed to 380px, and one further keystroke
repaired it.

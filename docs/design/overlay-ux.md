# Overlay UX & visual language

The design source of truth for the Cortex body overlay (Slice 8, [ADR-0011](../adr/ADR-0011-body-v1.md)).
Agents building or changing overlay components follow this; deviations need a note here first.
It describes the **target** experience and marks what ships in v1 vs. what waits on the seam.

## 1. Identity and what it should feel like

A **sleek, modern** assistant you summon in a keystroke and dismiss without a thought. One that
**comes alive with color while it works**.

**The core rule: color is the signal of *activity*.** At rest the overlay is calm and
near-monochrome: a clean glass surface, restrained type, one quiet chosen neutral, no gradients on
resting chrome or composed messages. **Color (the accent gradient) is reserved for *working*
affordances**: a model thinking, text streaming in, the minimized orb, progress. So "the assistant
is alive / doing something" reads at a glance, and the resting UI stays modern and out of the way.

Three adjectives, in priority order: **sleek** (minimal, precise, current, never loud at rest),
**alive** (it breathes, streams fluidly, and *blooms* with color while thinking), **bubbly** (soft,
rounded, springy shapes and motion, friendly and never sharp). It ships **light and dark** from day
one and is **theme-customizable** later (a token swap). It is an *overlay*, not an app: fast to
summon, effortless to dismiss, and it never nags. Motion is fluid and purposeful: text *streams* in
rather than popping, the panel *travels* when it minimizes/maximizes, and the orb's bubble *warps*
as its film turns under the light. All of it respects `prefers-reduced-motion`.

## 2. Visual language (design tokens)

Everything is CSS custom properties, so the whole surface restyles from one place and a theme
is a token swap, not a rewrite. **The whole surface crosses together, over 400ms** (2026-07-21):
one transition is put on everything for the length of the crossing, because otherwise each control
crosses at whatever pace its own hover transition uses, the text beside it (which transitions
nothing) takes the new value at once, and the two lines that inherit the ground's colour follow the
ground. One swap at three speeds reads as the window coming apart and going back together.

- **Two grounds, light and dark, both sleek** (mandatory in v1). Switched by `[data-theme]` (with
  `prefers-color-scheme` as the default). Both are frosted glass with `backdrop-filter: blur(28px)
  saturate(140%)`, over a *chosen* neutral biased a hair toward the accent, never a pure grey:
  - Dark: `--panel: rgba(18,16,28,0.72)`, text `#F3F1FA`, muted lavender-grey `#A79FC4`, hairline
    `rgba(255,255,255,0.10)`.
  - Light: `--panel: rgba(250,250,253,0.72)`, text `#1A1726`, muted cool-grey `#6C6880`, hairline
    `rgba(20,16,40,0.10)`.
  - **Custom themes are a later token-swap** (user-defined `--panel`/`--text`/`--accent` sets).
- **Accent gradient (activity only).** `--accent: linear-gradient(135deg, #8B5CF6, #E24BC4 52%,
  #FF7A6B)` plus a mint spark `--spark: #4FE3D0`. It appears **only** on *working* affordances: the
  breath mist that rides a streaming reply (§2 motion, [ADR-0037](../adr/ADR-0037-whisper-streaming.md)),
  the minimized orb, and progress bars. It **never** touches resting chrome, buttons, or composed
  messages, the single most important rule (see §1). Exact hues are provisional; keep it a
  warm-leaning gradient.
- **Bubbles (neutral at rest).** Both user and assistant bubbles use a quiet raised neutral fill
  (a subtle tint of the ground, e.g. `rgba(127,110,190,0.14)` for the user in dark). The **only**
  color is *transient*: while a reply streams, the whisper's accent mist rides the condensation
  front inside the bubble and evaporates on completion
  ([ADR-0037](../adr/ADR-0037-whisper-streaming.md)); the bubble itself wears no glow, ring or
  caret, so the colour sits exactly where the work is and nowhere else.
  `border-radius: 20px`, one tail corner tightened.
- **Radius scale:** panel `28px`, bubbles `20px`, input pill `22px`; the orb is the bubble mark
  (§4), an off-round film rather than a disc, so it has no radius of its own. Generous, uniform.
- **The window's edge is a choice, a ladder of dream depth** (landed 2026-07-21,
  [ADR-0036](../adr/ADR-0036-window-edge.md)): a third registry beside the theme and the mark,
  one more swatch row in the console, and the two families speak sibling languages: the mark
  thinks, the window dreams. **Still** is today's crisp glass as a real choice; **Lucid** (the
  default, by the user's call) melts the silhouette with the mark's own maths, integer wave
  orders on the closed perimeter so the seam never tears and the shape never drifts, and keeps
  the color story strict; **Reverie** adds a smolder riding the outline, neutral at rest, taking
  the accent gradient while a turn runs; **Trance** thickens the spectrum and keeps a low ember
  of the gradient lit at rest, **the one written exception to §1's color rule**, chosen with its
  cost on the table. The registry's order is the explanation, so the tile row needs no caption.
  Three build truths carry the look: the animated clip lives on a background-only glass slab and
  the words never ride the warping layer (which is what keeps type sharp), the blurred smolder
  paints under the content so nothing soft crosses a glyph, and a liquid panel trades its
  backdrop blur for the near-solid `--panel-solid` token because Chromium composites the blur
  un-clipped by a path (invisible in the v1 opaque window; refiled with the transparent-window
  pass in [refinements/body-overlay.md](../refinements/body-overlay.md)).
- **Scrollbars are reserved chrome, never a widget** (landed 2026-07-20). Every scroll region (the
  history, the switcher, the reminder stack, an open Thoughts trace, an approval draft, the
  console's rows, the composer field) wears one `--rail: 6px` bar: a rounded 4px thumb
  mixed out of `--muted` at 38%, 62% under the pointer, on a transparent track, no arrows, no
  corner square, and held 6px off both ends so it never meets a rounded corner. Resting chrome, so
  no accent, ever. The rail's width is **reserved whether or not the region is scrolling**: a reply
  spilling past the bottom must not re-wrap the paragraph above it or shove every bubble sideways.
  Where a region already had enough inline-end padding to hold the rail, it is paid for out of that
  padding and the margin stays the number it is on the other side (history and rows 16px, switcher
  and reminder stack 6px, all unchanged). Three of the seven had 2px or none, and there the rail is
  added on top instead, because the point of reserving it is that text clears the thumb: the
  Thoughts trace, the approval draft, and the composer field each sit at a 12px inline-end inset
  now. Reserving buys one axis: the gutter is inline-end, so a *horizontal* bar is unfunded and
  takes its height straight out of the region, shoving everything up. Nothing is allowed to grow
  sideways instead. Every region showing text it did not author breaks long tokens
  (`overflow-wrap: anywhere`), so a 64-char commit hash or a `.gguf` filename wraps inside a bubble
  rather than widening it, and the history clips that axis outright rather than trust future
  content. Chromium (WebView2) is the engine that ships, so `::-webkit-scrollbar`
  is the path that matters; `scrollbar-width` / `scrollbar-color` are fenced behind `@supports not
  selector(::-webkit-scrollbar)` for the engines that have no pseudo-elements, because Chromium
  honours the standards properties *over* them when both are set (measured: `thin` reserves 10px
  beside a 6px webkit rail), which would leave every padding subtraction 4px wrong. On the fenced
  engines the UA picks `thin`'s width, so the subtraction does not balance there either and the
  inline-end margin reads a few px wider than the other side. Nothing shifts when the bar appears,
  which is the property that matters; Firefox is not a target, so the asymmetry is accepted rather
  than given its own numbers. That one and the switcher/reminder cards spending their whole 6px
  inset on the rail are the two tradeoffs this pass accepts, and both are filed with their triggers
  and their fixes in [refinements/body-overlay.md](../refinements/body-overlay.md) and at
  [ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 22.
- **Typography:** a clean modern sans for everything (system stack in v1; a licensed sans inlined
  as a `@font-face` data URI later; no CDN). Assistant text ~15px/1.5, never cramped. Sleek, not
  decorative. The personality is in motion + the color bloom, not a novelty face.
- **Motion:** `--spring: cubic-bezier(.34,1.56,.64,1)` for shape; `--ease: cubic-bezier(.4,0,.2,1)`
  for fades. Three signatures, detailed in §4:
  - **Whispered streaming** ([ADR-0037](../adr/ADR-0037-whisper-streaming.md), replacing the
    per-word rise + blur this doc used to prescribe). The reply *condenses like breath on
    glass*: letters clear through a nine-letter band of blur on one continuous front whose
    velocity eases toward its backlog and never resets (paced not timed, per letter), so
    nothing resolves as a block. A small accent mist breathes where the text will start, glides
    along the front while the reply speaks (one element, breath to front to evaporation, a
    morph with no swap anywhere in the lifecycle), and is the bubble's only colour. The
    bubble's box is posed by the same clock: a small pill around the mist while thinking, then
    growth eased at the front's own pace, its bottom edge doubling as the reveal, so a new line
    is a curve rather than a step.
  - **Traveling morph**. Minimize/maximize animate real *movement*: the panel glides along a path
    between center and the corner while it scales to/from the orb (FLIP), so you see it travel.
  - **Arriving centred, growing upward, re-centring only into another view**. A summon centres the
    panel on what it arrives with, for the length of its own pop: the day's reminders are pulled on
    that same rising edge and roll in a frame later, and the panel appearing with them in it is not
    the same thing as the panel growing afterwards. That hold ends early the moment the user
    touches the panel, because a list they opened a beat after it appeared is a height they are
    about to hand back, and centring on it would leave the panel low for the rest of the session.
    From then on it is anchored by its BOTTOM edge,
    so a reply arriving, the switcher opening, a reminder landing, or the pencil emptying the panel
    resizes it from that edge and the composer never moves under the hand that just typed; it stops
    at `12vh` of clear space and simply stops getting taller there, the history giving the room up
    instead. That is the ONE bound and it is on the height, not on the edge: nothing walks the
    bottom edge down to buy a taller panel, so the composer holds still at the ceiling exactly as it
    does below it (measured 2026-08-06 at 640x720 and 900x900, 0px on every frame of an ack, a
    switcher round trip and a shrink clean off the ceiling). The edge it is pinned to is remembered
    UNCLAMPED, which is what makes a grow-then-shrink round trip land back on the identical edge and
    height. **The edge nearest the hand is the edge that holds still**, which is that bottom
    one for the chat and the TOP one for every other view: the console's chrome is its back button
    and its tab strip, so a tab change grows the panel downward and the strip never moves under
    the cursor that clicked it. A view of more than one shape (the console, whose tabs differ in
    height) arrives at the top its TALLEST shape would take, so the strip sits at one height
    whichever button opened it and a shorter tab simply ends higher. Entering resizes the panel
    from the edge the chat is standing on (user call 2026-07-21: it shipped sliding to true
    centre, and the slide is kept one flip away behind `VIEW_CHANGE_RECENTRES` in
    `panelPlacement.ts`, both settings under test); coming BACK to the
    chat restores the edge the chat was left at, which the standing edge now makes trivial, and
    the parked edge still guarantees the moment the slide is switched back on
    ([ADR-0033](../adr/ADR-0033-panel-growth.md),
    [ADR-0034](../adr/ADR-0034-panel-views.md) and its addendum). Another chat is not another
    view: it resizes in place. All of it is measured and replayed in code, not a CSS transition: `height: auto` to
    `height: auto` is not a computed-value change, so a transition never fires (and
    `interpolate-size` does not help, being for `auto` against a length).
  - **Motion is paced, not timed, and a move in the air is resumed rather than restarted**. A move
    takes as long as its distance warrants, one constant pace between a 120ms floor and a 380ms
    ceiling, so a line of streamed text settles at the floor and a whole view changing takes the
    full time. One fixed duration cannot do both: every token re-renders the panel, so at 380ms it
    never converged and visibly trailed the text it was growing to fit. Pacing alone does not fix
    that, only shorten it, since a token still lands well inside the floor: what holds the landing
    still is that a render which does not change where the panel is going carries on the move
    already running over the time it had left. A line of growth then lands 120ms after it appeared,
    whatever arrives while it is landing.
  - **Rolling sections**. A section that comes and goes (the switcher list, the reminder stack, a
    reply's Thoughts trace)
    animates its OWN height between nothing and its content, staying mounted through the close. The
    panel's height follows it frame by frame, so the list rolls up and the panel's top edge comes
    down with it while nothing else on screen moves. Deleting the rows and letting the panel catch
    up afterwards is the thing this replaced, and it read as a glitch. The closing roll HOLDS its
    collapsed height until React removes the element, or the section snaps back to full size for
    the frame in between; where nothing animates at all (`prefers-reduced-motion`) the collapsed
    height is committed by hand instead, since there is no fill to hold it. When the roll would
    carry the panel past its ceiling, the panel takes its own bottom edge along over that same
    roll, which holds the top edge still instead of correcting itself in a second beat afterwards.
    A move of the panel's own that is still in the air when the roll starts is carried through it
    rather than cancelled, so the panel never hands a half finished height back to layout and jumps
    in a single frame. **The roll says out loud that it has begun** (landed 2026-07-20), because
    not every section is one the panel re-renders with: the trace's open state belongs to its own
    message, so without that word the panel heard only the end of the roll, snapped back to the
    height it remembered from before it, and made a second movement out of one. A chat change is
    a content swap, not a section toggle: the reminder stack is keyed to its session, so a new
    chat carries the stack in with the emptied panel's one movement instead of rolling it open
    over the leaving conversation, which read as a jump (landed 2026-07-21). **A roll INSIDE the
    conversation carries the log with it** (landed 2026-08-03): once the panel is at its ceiling it
    has nothing left to absorb a trace with, so the growth goes into the scroll and takes the end of
    the reply under the composer. For a reader who is at the end of the log, the history holds that
    same distance for every frame of the roll and hands the growth to the scroll instead, capped so
    the trace's own top edge never leaves the window; for a reader who has scrolled up it does
    nothing, since nothing they are looking at moves and the row should stay under the pointer that
    opened it. The wheel outranks it, and under `prefers-reduced-motion` there is no roll to carry.
    **A roll in the panel's CHROME carries it the same way** (landed 2026-08-04): the switcher list
    and the reminder stack take the log's window where a trace takes its content, which costs the
    reader the same 220px of reply at the ceiling, so the same rule answers both. The one difference
    is the cap, which is about keeping what you opened in view and therefore means nothing for a
    section that is not in the log at all.
  - **A warping bubble**. The orb's mark is a soap bubble whose outline warps on its own clock
    while the film turns under a fixed highlight; the anchor point holds rock still (no breathing
    scale, no positional drift, per 2026-07-03 user refinements), so it reads as alive without
    wandering. The stillness is structural, not a rule to remember: every harmonic is of order two
    or higher, which fixes the centroid and the mean radius (§4, ADR-0031).
  - Durations: micro 120ms, standard 240ms, morph ~360ms. `prefers-reduced-motion: reduce` →
    collapse to ≤120ms opacity fades, no travel, the mark frozen at a still pose with no
    animation frames scheduled at all.

## 3. Anatomy of the panel

Top-to-bottom, the summoned panel is:

1. **Header** is the current chat's title (auto-derived from its first message; "New chat" until
   then) and a set of **outline icon buttons that share one vocabulary** (1.7px round-cap strokes
   on a 24 grid, `currentColor`, hollow, in `components/icons.tsx` + `ThemeIcon.tsx`; 2026-07-07
   revision): a **chat-switcher** (two speech bubbles) opening the recent-chats list, lit while
   open (`aria-expanded`); the **theme toggle** (an outline sun that *morphs* into an outline
   crescent, as the two forms cross-fade and spin, the rays retract; never a glyph swap); a **new
   chat** (pencil for "compose a new one"); and **dismiss** (a downward "tuck-away" chevron, since
   dismissing only hides; the chat is saved and re-summoning restores it, so the glyph tells the
   truth, not an `×`). A **connection indicator** opens the button cluster, immediately left of
   the switcher (landed 2026-07-16; it led the row until 2026-07-20): a 7px dot,
   green when the brain answered ready, **amber when it answered and is not serving** (a non-OK
   status, an unreadable reply, or a future not-ready health reply), red when nothing answered,
   and neutral before anything has been asked. While a probe is out it keeps the last known
   colour and pulses, so a reconnect neither flashes green nor forgets it was red; a routine
   probe on a healthy link does not pulse at all. Its label is both the tooltip and the
   accessible name, because a colour alone explains nothing. v1 shipped this as an always-green
   decoration and the 2026-07-03 pass removed it: chrome earns its place by meaning something,
   and the difference now is that the signal is real (ADR-0011 addendum: derived from the turn's
   own events, a probe per summon, and a recovery re-check only while an unhealthy link is on
   screen, never a poll on a timer). The three status hues come from the mark's own palette,
   deepened in the light theme; they are the only colour in the overlay that is not activity.
   The **screen-capture ring** (ADR-0029, `components/CaptureDot.tsx`) sits next to it and moved
   with it, because the two are **one row of state** rather than two ornaments: left at the title
   the ring would be the one mark there, appearing and vanishing with every capture, while beside
   the buttons the pair reads as "what the panel currently is" next to "what you can do to it".
   **The title therefore starts the row** (2026-07-20,
   [ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 23), and it is inset **31px** from
   the panel's edge rather than the header's bare 16px, which balances it against the 28px corner:
   the title's own centre is already 31px below the top edge, so the first glyph sits on the
   corner's 45-degree diagonal, as far from the side of the panel as from the top of it (on the
   bare padding it is 17px in against 31px down, and the curve turns through the short gap). That
   inset is also the panel's text rail, measured in Chromium: a switcher row's title starts at
   31px, an assistant bubble's first glyph at 32px, the composer's text at 33px, so the open
   chat's title now lines up with the list of the other chats that rolls open directly under it,
   and with the reply beside it. Every other view opens with the back button instead, which
   supplies its own inset, so the rule is scoped to a title that actually starts the row.
2. **History** is the scrollable conversation: alternating user/assistant bubbles, newest at the
   bottom, auto-scrolling as tokens stream (but *not* if the user has scrolled up to read;
   landed 2026-07-12). Tool-activity and status appear as slim inline chips between bubbles
   ("📧 reading inbox…", "swapping model…"), not as bubbles (landed 2026-07-12: a neutral pill
   with a pulsing accent dot, above the streaming bubble, gone on completion). A `"thinking"`
   status chip reads distinctly (landed 2026-07-13: `chip-think`, the dot carrying the reasoning
   bob and the label the accent, so deliberation is not mistaken for tool action). The **approval
   card** (§4, ADR-0022) is this inline layer's first real occupant. Empty state: the mark +
   "Ask me anything" + a couple of example prompts as tappable chips (landed 2026-07-12). The
   mark here is also the **mark picker** (§4, ADR-0031): clicking it opens the bubble styles,
   drawn live, and choosing one applies to the empty state and the orb at once. **The empty state
   is also the chat's floor** (landed 2026-07-20, [ADR-0035](../adr/ADR-0035-console-and-motion.md)
   decision 12): the first send used to shrink the panel, because a user bubble and a thinking one
   are less content than the invitation they replace (traced: 546px to 457px in 150ms). The column
   of bubbles keeps a minimum of the empty state's own measured height, so a chat can only ever
   grow from the panel that invited it. The reserved height sits *above* the bubbles, which puts
   the newest one against the composer and keeps it the thing the auto-scroll follows. One measured
   number can only be that floor while the invitation is one height, so the example chips are held
   to a single row and shrink to an ellipsis rather than wrapping onto a second. Since 2026-08-03
   the floor is measured rather than transcribed (the same ADR's chat-floor addendum): the empty
   state publishes its own box as `--chat-floor` while it is on screen, which is every moment before
   the first message, so an edit to the mark, the invitation or the chips moves the floor with it.
   That sentence was briefly untrue: the floor was removed on 2026-07-20 and the first message
   dropped the panel 90px for fourteen days. **The end of a
   turn is floored the same way** (landed 2026-07-20,
   [ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 13): the live chip and the collapsed
   Thoughts disclosure that replaces it are one row in two states, so they are the same height and
   the answer landing does not resize the panel it lands in. Measured off the chip itself since
   2026-08-03, by the same probe: the chip is the row and the disclosure floors on what it says. **That disclosure rolls** (landed
   2026-07-20): it is a button over a rolling section rather than a `<details>`, which reveals its
   content in one frame and cannot be talked into animating it, and the `›` turns over the same
   300ms so the marker and the trace are one movement. Opening it leaves the history's scroll
   position alone: the row stays under the pointer that clicked it and the trace unfolds beneath,
   which is worth more than keeping the reply in view when the panel is already at its ceiling.
   That is the app's decision rather than the engine's, the history having turned Chromium's scroll
   anchoring off after it was caught lurching the log by the trace's height on the frame a roll
   starts ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 15).
3. **Composer** is a rounded pill textarea (`⏎` sends, `⇧⏎` newlines, auto-grows to a few lines;
   grow + focus-on-summon landed 2026-07-12),
   a glowing accent focus ring when active, and a gradient **send** button (an outline up-arrow,
   `components/icons.tsx`) that springs on press; its gradient **fades in** as the field gains
   content (an opacity overlay, since gradients can't interpolate, and a hard swap pops). **On hover
   the glyph moves and the cap does not** (landed 2026-07-20): the arrow rises 3px, the way the
   message goes, so the button says what it is about to do rather than only acknowledging the
   pointer. The maintainer picked it over three hovers that move the cap itself (lift, swell, and a fill
   blooming from the middle), and it is also the only one that leaves the pill's geometry alone. A
   **live** button keeps its white glyph through the hover: white is what makes it legible on the
   accent gradient, and handing it back the text colour put a near black arrow on a magenta cap in
   the light theme. **While streaming the button is a real stop** (a filled square, lit): it cancels
   the turn. Hovered, the stop **turns red** (`--halt`) and the square eases shut rather than
   travelling, having no direction to go in. That is the one hover in the overlay that changes hue,
   and it is meaning rather than decoration: the button has swapped what it MEANS, from how a turn
   begins to how one is called off, and grey said only "a button". The red is the same one the
   trash on a chat row wears, the two controls in the overlay that undo something in flight. A `stop`
   reducer action drops the bridge stream and ends the reply in place, keeping the partial text
   (distinct from dismiss, which minimizes to the orb). Landed 2026-07-07. **Past one line the pill
   is two rows** (landed 2026-07-20, [ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 17): as a
   flex sibling of the field the button reserves its 44px column down the whole pill, which one
   line hides and several do not, every wrapped line stopping short of the right edge and the
   button floating alone at the bottom of a tall empty column at the field's 120px ceiling. Past
   one line the field spans the pill (475px to 519px at the shipping 560px) and the button drops
   to its own row beneath, still at the end, where the eye already looks for it. The **button does
   not move** in either direction: both layouts leave it in the same corner of the same content
   box, traced at `[671,637,38,38]` for every one of the 183 characters of two lines typed one key
   at a time, each with exactly one layout flip and no intermediate frame. Which layout to use is
   decided at **one** width, the inline one, whatever layout is on screen, because a stacked field
   is wider and a draft that just wrapped would fit again the moment the button left its side:
   asked at the width in use the two layouts answer each other forever. The band where that matters
   is five or six characters wide and where it starts depends on the glyphs (60 through 65 on one
   traced line, 62 through 66 on another), and inside it the pill is one row roomier than its text
   needs, which is the better of the two ways to be wrong there. **A pill with nowhere left to grow
   shrinks its own window rather than pushing the chrome off the panel** (landed 2026-07-20,
   [ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 19): with the switcher open and the reminder
   stack up at the body's window, a draft at the field's ceiling used to put the send button and
   the whole hint strip past the panel's clipped edge, and now the field scrolls a shorter window
   instead, down to one visible row before anything else gives. **A window that cuts a line fades
   it** (landed 2026-07-20, [ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 20): the field
   scrolls in both of those states and neither bound is a whole number of line boxes, so the edge
   line used to be sliced horizontally through its glyphs. The field's own 9px padding is a fade
   band at each end instead, free while the text is inside its window because the band holds nothing
   but padding, and the caret's line is kept out of it, so the line being typed is never the faded
   one.
4. **Hint strip** is a subtle one-line footer of the live shortcuts (§6), dimmed and **centered**,
   with two openers at its end, each landing on the tab it names: a **sliders** button for
   **appearance** (landed 2026-07-19, [ADR-0032](../adr/ADR-0032-preference-record.md)) and a `?`
   for the full shortcut list (landed 2026-07-12; the `?` key works too, outside the composer).
   Both open **the console**, one **view the panel morphs into** rather than a sheet laid over it
   (2026-07-19, [ADR-0034](../adr/ADR-0034-panel-views.md)): the panel resizes to what the view
   needs on the edge the chat is standing on (the slide back to true centre it shipped with is a
   user-reversed flip away; see the ADR's addendum), so a console tab with two rows of swatches
   in it is a small window rather than a tall one with its footer stranded three hundred pixels
   below the content. **Esc leaves it in one press** (2026-07-20,
   [ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 1), because the two sheets that used
   to stack are one view with a tab strip now. The kbd glyphs are outline icons matching the header set
   (return / shift / cycle chevrons), not raw Unicode symbols (2026-07-07).

## 4. The interaction state machine (the heart)

The overlay is a small, explicit state machine. The **user's signature behavior** (*dismissing
while a turn is processing must not lose it*) lives here. States:

```
        summon (hotkey)                     submit
 HIDDEN ───────────────▶ PANEL(composing) ─────────▶ PANEL(streaming)
   ▲                          │  ▲                      │        │
   │ dismiss (idle)           │  │ click orb / hotkey   │        │ complete/failed
   └──────────────────────────┘  └───────────┬─────────┘        ▼
                              dismiss (Esc / click-away) │   PANEL(done)
                                    while streaming ─────┘        │ dismiss (idle)
                                          │                       ▼
                                          ▼                    HIDDEN
                                   ORB(thinking) ──complete──▶ PREVIEW ──auto (Ns)──▶ HIDDEN
                                          ▲                       │
                                          └──── click ────────────┘ (→ PANEL(done))
```

- **PANEL(composing / streaming / done):** the full centered panel, sleek and near-monochrome at
  rest (composing/done). **Streaming** is where color blooms, and the bloom is the whisper
  ([ADR-0037](../adr/ADR-0037-whisper-streaming.md)): the accent mist breathes in a small
  bubble until the first token, then the reply **condenses** behind it, letters clearing
  through a continuous band of blur while the mist glides along the front and the bubble grows
  at that front's pace; when the turn completes the mist evaporates where the last word ends
  and the bubble is already neutral. No caret, no dots, no glow: the mist is the streaming
  bubble's one colour.
- **Dismiss while idle** (composing or done): the panel springs out **at center** (a scale-fade,
  no corner travel, per 2026-07-03 user direction; summon pops in from center the same way) →
  **HIDDEN**. Nothing is lost, because the chat is persisted; re-summoning restores it. The corner
  travel is reserved for the orb morph below.
- **Dismiss while streaming** (Esc or click-away): the panel **morphs**, scaling and gliding down
  to a corner (default **bottom-right**, configurable), shedding its chrome, into a small **ORB**.
  This is one continuous transform (FLIP-style), not a disappear-then-appear, and the reverse
  (maximize) *travels* it back from the corner to center. You always **see it move**, both ways.
- **ORB(thinking):** the **bubble mark** at the corner (~64px; replaced the living rings
  2026-07-19, ADR-0031, because concentric turning rings read as another product's identity). It
  is a soap bubble: an off-round film, lit from the upper left by a light that never moves, with
  the **same eight-stop gradient** the rings carried (the user's palette is one gradient, not two
  arcs: `#43d675 #ffb347 #ff5f6d #e055d8 #3fa2ff #6a5cff #c44fd8 #ffd23f`) stroked thickly just
  inside the rim, where a real film thins and colors, over a soft bloom. Its outline is a circle
  modulated by sine harmonics, all of order two or higher, so the **centroid and the mean radius
  are fixed by the maths**: no breathing scale, no positional drift, the anchor holds still while
  the shape moves. Under reduced motion the mark freezes at a still pose and schedules no frames.
  It reads as alive, not a static badge, and means "still working." **Click** it → morph back to
  **PANEL(streaming)** (the in-progress turn, right where it is). It never covers active work,
  thanks to small, corner-pinned, click-through-safe margins.
- **Which bubble is a choice** (ADR-0031), and the choices are named as movements of thought:
  the mark is the overlay's thinking signal, so the picker asks "how does it think?" and each
  label answers with how that style moves. Four ship: **Mull** (two slow modes turn the outline
  over; the default), **Muse** (near circular, the film drifting beneath a calm surface),
  **Hunch** (still, until a ripple strikes the rim and fades), **Tangent** (two side thoughts
  swinging on slow arcs around the main one). Each is stored under a key matching its label
  (mull, muse, hunch, tangent): the keys a style first shipped under (wobble, sheen, ping, foam)
  were healed to match on 2026-07-21, once the maintainer confirmed nothing beyond his machine holds a
  stored value, and they live on as resolver aliases so an old stored pick still lands. They are
  data in a registry (`mark/marks.ts`), the twin of the theme registry, so a fifth is a literal
  and no code. The picker is the empty state's own mark: clicking it opens the styles drawn live, rather
  than adding a fifth header button that would put the accent palette on resting chrome.
- **CONSOLE:** the panel's one other face, everything about the overlay that is not the
  conversation, behind a chevron back to the chat and a **tab strip** (2026-07-20,
  [ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 1). It replaced two separate views, so Esc
  leaves in **one** press and there is no precedence to remember.
  - **Face** (the appearance tab; named 2026-07-21, with the whole console strip: the two tabs
    read **Face · Chords**, what it shows and what you play on it, per the AGENTS.md naming rule;
    2026-07-19, [ADR-0032](../adr/ADR-0032-preference-record.md)) is opened by the hint strip's
    sliders button or by the empty state's own mark, which is the shortcut to the row that
    changes it. Three rows of **swatches** whose legends name the dimension each varies along,
    one anatomy (the face has a light, an iris, and a dream), each choice made by looking at the
    thing rather than reading its name: **Light** is the theme as tiles that are miniatures of
    the panel wearing it, drawn from that theme's own tokens, with **Auto** as a tile split
    diagonally between the two themes Auto resolves to (still the only place Auto can be chosen,
    since the header's toggle names the opposite theme outright and can only land on one of the
    two); **Iris** is the mark as tiles drawing the real bubble at 40px, with the chosen style's
    note under the row, because these four differ by how they MOVE; **Dream** is the window edge
    (§2), drawn as portraits: the Light row's miniature window with its outline gone liquid, the
    amplitude re-tuned for the swatch, and Reverie's tile cycling between its two states so it
    does not read as a lighter Trance (ADR-0036 addendum). Every row is a map over its registry, so a fifth entry appears here with no change to
    the view. Every choice persists to the brain's own settings record, so it outlives a restart
    and a reinstall of the body.
  - **Chords** is the complete binding list, grouped (Ink / Chats / The window) on the row
    rhythm the console shares: what it is on the left, the keys on the right, hairlines between.
    Each key is its own cap and a non-letter cap carries the header's own outline glyph, exactly as
    the hint strip draws them.
  - Selection is a **lift** (a fill and a hairline), never an accent: a console is resting chrome
    even when the thing it draws is not, so the only colour on that surface is the marks
    themselves. There is no backdrop to click away from.
  - **Switching tabs is the panel's one morph** (it resizes downward from a held top edge), and the
    crossing between two tabs is a **pure fade**: the header and the strip are the same chrome in
    the same place in both, so they hold still, pixel for pixel, while the content changes under
    them. Only a change between the chat and the console keeps the small rise-and-sink, since those
    two share nothing. **Focus travels with the view**: into the console it lands on the tab that is
    up (the strip that was clicked leaves with its pane), and out of the console it returns to the
    composer with the draft and its caret intact, which is where a summon puts it too. That is also
    what lets the pane on its way out be hidden from assistive tech, so only one console is ever
    announced while two are on screen.
  - **The strip is a tab list from the keyboard too** (2026-08-03,
    [ADR-0035](../adr/ADR-0035-console-and-motion.md) addendum). Tab reaches the whole strip as
    **one** stop and arrives on the face that is up; **←** and **→** walk along it and wrap round at
    both ends; **Home** and **End** go to the first and last face and stop there. **Selection
    follows focus**, so one arrow both moves the keyboard and changes the view, exactly as one click
    does, which the console can afford because both faces are already mounted and at the shipping
    spread they share a height, so the arrow changes the content and not the panel's size. The
    vertical arrows are left alone, Ctrl with those being how chats cycle. **What is hidden is
    unreachable**: the pane on its way out, the face not showing, and the whole panel while it is
    dismissed are each taken out of the tab order in the same frame they leave the accessibility
    tree, so Tab pressed during a 380ms morph cannot land in the view being left and Tab pressed on
    a dismissed panel finds nothing at all.
- **PREVIEW:** when the turn **completes while minimized**, the orb **expands** into a compact
  card near the corner: the answer (a few-line clamp) and a hairline accent progress bar
  counting down the auto-dismiss (~6s) and **nothing else** (the "reply ready"/"click to open"
  captions and then the mini mark were removed 2026-07-03 as redundant: the card appearing *is*
  the signal, and the draining bar says it will go). **Hover pauses** the countdown (landed
  2026-07-12: the fade timer itself pauses, not just the bar; leaving restarts the full
  countdown rather than resuming, with the drain bar remounting in step, so what the bar shows
  always matches the timer); **click**
  morphs to **PANEL(done)** (full answer in context); ignore it and it **fades out** → HIDDEN
  (still persisted). A failed turn previews as a soft error card (same shape, red-tinted) that
  does *not* auto-fade, because errors wait to be seen. **The card always dreams, and always in
  Lucid** (2026-07-21, [ADR-0036](../adr/ADR-0036-window-edge.md)), whatever the Dream row is
  set to: it is the one surface that arrives unbidden over whatever the user is working in, so
  a soft edge is what keeps it from reading as a system notification, and the two louder styles
  carry colour, which on a card announcing work that has just *finished* would say the opposite
  of what §1 reserves colour for.
- Re-summoning the hotkey from HIDDEN always returns to **PANEL** on the current chat.

This gives the "fire it, keep working, glance when it pings me" flow the maintainer asked for, and it
is coherent with the hard rule: dismissing is purely a *view* change. The turn keeps streaming to
the store, so nothing depends on the window staying open.

**The approval card (Slice 8.8, [ADR-0022](../adr/ADR-0022-email-write-confirmer.md)).** A gated
(outbound/irreversible) tool call pauses its turn mid-stream on the user's explicit approval; the
card is that question. It renders in the **history's inline layer** (below the streaming bubble),
neutral like the rest of the resting chrome: an outline shield + the tool name, the draft's
fields as **verbatim** key→value lines (falling back to the raw JSON string if the arguments
aren't one JSON object, since what you approve is what runs, so nothing is prettified away), the
brain's reason line, and **Deny / Approve**. Approve is the one place the accent gradient
appears. It is the working affordance that runs the action; Deny stays neutral. Semantics:
**Approve** sends the answer back over the turn's stream and the tool runs; **Deny** returns a
user-declined result the model relays; either way the card leaves immediately (a second click is
a no-op). Everything else is a deny by **fail-closed** construction: dismissing, stopping the
turn, switching chats, or simply walking away all drop or abandon the question, and the brain
denies on its own timeout. **A question the brain has closed leaves the screen too**: when it
stops waiting (its timeout, or its input stream ending) it says so, and the card goes without
waiting for the turn to end, because a card that can no longer be answered is a lie and a click
on it would look like it did something. The explanation is the reply itself, which resumes
saying the action was not performed; the card does not linger to repeat it. Nothing ever runs without an explicit Approve. Two rules carry over
from the machine above: a confirm arriving **while minimized** surfaces the preview exactly like
a completed turn, but the preview **does not auto-fade** while the question is open ("errors wait
to be seen" extends to questions, so the countdown starts once it resolves); and only a **live**
turn can raise the card. A cancelled turn's late request changes nothing.

**v1 window scope (Slice 8).** This whole state machine ships in v1, but it runs *inside* a fixed,
frameless, **opaque** always-on-top window (640×720, centered): the panel/orb/preview live within
that window and every morph/drift/preview animation plays there. The **OS-window-level** moves are
deferred to a later overlay-polish pass, to be done together: a **transparent** window so only the
panel floats over the desktop (a first pass bled through the panel and left a window border, so it
waits to be done properly with **click-through** on the empty margins), morphing the window to a
true *screen* corner (v1's orb sits at the window's own corner), and **hide-on-blur** (v1 toggles
with the hotkey instead). Host bring-up and the running list of these deferrals live in
[body-overlay.md](../runbooks/body-overlay.md).

## 5. Chats, history, and sessions

**A chat is a session.** Each chat maps to a `session_id`; the brain persists that session's
messages (`SessionStore`, the hard rule), so history is durable and survives model swaps and app
restarts. The overlay is a *view* of store-backed state, never the user of it.

- **New chat** (＋ / `Ctrl+N`): mint a fresh `session_id`, clear the panel to the empty state. The
  previous chat is already saved.
- **Cycle chats** (`Ctrl+↑` / `Ctrl+↓`): move through recent chats, newest first; the switcher (⌄)
  opens a slim list with titles + relative timestamps + a one-line preview. Selecting loads that
  chat's history. **A row runs title and preview on the left, then right to left: the time, the pin,
  the pencil, the trash** (2026-07-21). The time takes the edge because it is what the eye goes to
  when it is skimming for a chat, and the three controls sit inboard of it in the order they
  escalate; they stay ink-revealed on hover, so at rest a row is a title, a preview and a time. The
  time stands **11px inside the row's right edge, which is what the title stands inside its left**,
  so the two ends are one pair of margins rather than a label that happens to be near the corner.
  **Its width is reserved at 55px** and its text right-aligned in that box, so the column holds still
  while the clock runs and down a list of chats of different ages. 55 is a measurement of the four
  things `relativeTime` can say: `just now` 48.4, `59m ago` 50.9 (the widest that is bounded),
  `23h ago` 47, and the unbounded day branch at 47 for two digits and 54.3 for three, which is a chat
  pinned the better part of three years. A fourth digit pushes the column rather than being paid for
  by every row above it.
- **Titles:** derived from the first user message (later: a brain-generated summary title).

**Seam dependency delivered in [Slice 8.7](../ROADMAP.md) ([ADR-0021](../adr/ADR-0021-session-read-seam.md)).**
Listing chats and loading a chat's history require the brain to expose session data over the
seam. That landed:
- **v1 (Slice 8):** the overlay kept the **current app run's** chats + history in memory.
- **Now (Slice 8.7):** read-only `ListSessions` + `GetSessionMessages` RPCs feed the
  `BrainBridge` (`listSessions`/`sessionMessages`); `useOverlay` owns the `session_id` (minted per
  new chat), loads the list on mount + after each turn, and loads a chat's history on
  select/cycle. The chat list, the switcher (`⌄` / `Ctrl+K`), and `Ctrl+↑/↓` cycling are
  store-backed and survive restarts. **Cold start opens a new chat**; prior chats are reachable
  via the switcher and cycling (auto-restoring the most-recent chat on launch is a recorded
  deferral). Titles are still derived from the first user message (brain-generated summary
  titles remain a later refinement, deferred).

## 6. Keyboard shortcuts

Keyboard-first; the hint strip shows the contextually-relevant subset, `?` shows all.

| Keys | Action |
|---|---|
| `Ctrl+Alt+Space` (configurable) | Summon / focus the overlay |
| `Enter` | Send |
| `Shift+Enter` | Newline |
| `Esc` | Leave the console (one press, whichever tab), else dismiss (→ orb if a turn is streaming; else hide) |
| `Ctrl+N` | New chat |
| `Ctrl+↑` / `Ctrl+↓` | Previous / next chat |
| `Ctrl+K` | Chat switcher / command palette (palette is later) |
| `click orb` | Reopen the minimized turn |
| `?` | The console's shortcut list |

The hint strip under the composer carries the common bindings plus two openers into the console,
the sliders (appearance) and the `?`. It no longer lists `Esc`: the strip ran out of room when the
settings button joined it (measured at 573px of a 558px row), and Esc-to-dismiss is the most
guessable of the five. The console's shortcuts tab is the complete list, and it says both halves of
what Esc does, in the order the panel tries them. The strip draws a chord as the keys it is, one
cap each, which is the console's rule and now also the strip's own: `Shift`+`Return` was the last
place two glyphs shared one cap, and separating it costs 13px of a row with roughly 100 to spare.

**Every cap is at least as big as the widest and tallest single key** (landed 2026-07-21), in the
strip and on the shortcut cards alike, so a row of them lines up. Both floors are what a glyph cap
measures and neither is a chosen number: an outline arrow is 13px of drawing where an `N` is 8.2px
and a `?` is 5.8px, and it pads 2px where a letter pads 1. Left to themselves the six single keys
came out 23, 20.2, 19.2 and 17.8 wide, and a cap was 15 or 17 tall depending only on whether its key
happened to be drawn or written, which is why `Shift` and the return glyph beside it sat on
different lines. Both are minimums, so the named keys are untouched: `Alt` is already 26.9 wide and
`Space`, at 45.5, is the widest thing on either surface.

## 7. Accessibility & restraint

- **Reduced motion:** honor `prefers-reduced-motion` with no morphs/springs, just quick opacity
  fades; the orb still shows, its bubble held at a still pose (no frames scheduled at all), and a
  liquid window edge holds one exact pose per state the same way.
- **Focus:** the composer is focused on summon and on every return to the chat view, the console
  takes focus onto the tab it is showing, focus is trapped in the panel, and rings stay visible. A
  view on its way out is hidden from assistive tech, which is only true if focus left with it.
- **Contrast:** text on glass/gradient must clear WCAG AA. Verify bubble text over the accent.
- **Non-intrusive:** the orb/preview never steal focus from the app the user is using and stay
  out of the way (corner-pinned, small, dismissible). Sound is off by default.

## 8. How it maps to the architecture

- Components depend on the **`BrainBridge` port** (`src/bridge/types.ts`), never on Tauri directly
  (ADR-0011 addendum), so the whole UX runs in a browser against a fake bridge for dev + tests.
- The turn stream folds through the pure **`overlayState` reducer**; this design's broader machine
  (visibility mode + per-chat history + multi-chat) extends that pure core, so state logic stays
  100%-tested while animation lives in CSS (no JS branches to leave uncovered).
- `session_id` is the chat identity; new-chat/cycle operate on it; history is store-backed.

## 9. Decisions this design left to the user

Four of the five are settled; the list is kept whole so the reasoning is not lost. Host work that
is still outstanding lives in [docs/host/](../host/index.md).

- **Corner** for the minimized orb/preview defaults to bottom-right; top-right if the taskbar area
  is busy. (Configurable.) *Not decidable yet:* v1's orb sits at the fixed window's own corner, so
  this becomes a real choice only with the deferred window morph in section 4, and it is folded
  into that host-side pass.
- **Auto-dismiss timing** for the completed preview (default ~6s; hover-to-pause). *Settled
  2026-07-12:* the default and hover-to-pause both shipped, and the preview does not auto-fade
  while a confirm question is open.
- **Theme:** ship dark-glass only in v1, or also a light theme token set now? *Settled 2026-07-03:*
  both themes ship, with the toggle in the panel header.
- **Palette:** the violet→fuchsia→cyan accent is a starting proposal. Lock the exact hues.
  *Settled 2026-07-03:* locked to the user's one eight-stop gradient, which the connection dot's
  `ok`/`warn`/`bad` trio later drew from.
- **Sound:** a soft completion chime as an opt-in later, or never? *Still open*, and the only line
  here that is.

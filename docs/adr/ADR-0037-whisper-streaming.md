# ADR-0037: The reply whispers in, and the bubble grows at its pace

Date: 2026-07-21. Status: accepted.

## Context

The maintainer judged the shipped thinking and streaming effect out of the overlay's design language,
on four counts. The caret was a pulsing block cursor, terminal chrome in a language that says
bubbly and never sharp. The pre-token shimmer was three bobbing dots, every messenger's typing
indicator sitting in a product whose bespoke thinking signal is the mark. The lifecycle was three
states glued by hard swaps (dots vanish and words begin; the caret vanishes when the turn ends) in
an overlay where the sun morphs into the moon. And the per-word rise plus blur was the stock
reveal of the last two years of AI apps, carrying none of the family motifs. The design doc itself
prescribed that effect, so this ADR revises [overlay-ux.md](../design/overlay-ux.md) §1, §2 and §4
with it.

The replacement was picked over three rounds of a live artifact pitch, each round streaming real
demos on the overlay's own tokens. Round one named a family of four voices on the line "the mark
thinks, the window dreams, the reply speaks" (Murmur, Whisper, Patter, Intone, each a breath,
words and settle lifecycle whose breath element morphs into the leading edge). The maintainer picked
**Whisper**: the reply condenses like breath on glass, words resolving from a blur behind a small
accent mist, with no caret, no ring and no glow. The pick was first misread as Murmur because the
maintainer named the tile by position and the page had stacked its grid to one column; the lineup was
restored so the choice could be re-made by eye, which is the durable lesson for future pitches.
Round two smoothed Whisper's one flaw (whole words slammed into the mist as blocks) four ways, and
the user locked **Fog**: the mist survives the breath and glides along the condensation front as
its source. Round three fixed the two defects the user then called on the locked build, both of
one root, the bubble's box being raw layout: the out-of-flow mist let the empty waiting bubble
shrink-wrap to a sliver behind it, and arriving words claimed layout space the instant they
landed, so the box lurched by words and whole lines ahead of anything visible.

## Decision

1. **The reply's streaming effect is Whisper, one voice, not a registry.** The pitch names
   (the Voice family, and Fog against Hush, Dew and Sigh) were pitch handles and retire with the
   losing tiles; what lands is simply the overlay's streaming effect, and nothing freezes a
   storage key because nothing is stored. Making the voice a picked style beside the theme, the
   iris and the dream (the Face's fourth row) is a recorded refinement in
   [refinements/index.md#body-overlay](../refinements/index.md#body-overlay), viable because the effect
   lands behind one component seam.

2. **Letters condense on a continuous front, paced not timed.** The engine
   (`body/app/src/whisper/front.ts`, pure) holds one fractional position moving at one velocity.
   The velocity eases toward what the backlog warrants (backlog over 0.35s, clamped to 20..150
   letters per second) and is never reset, so arrivals only move the target: the panel's own
   motion rule (paced not timed, resumed not restarted) applied per letter. The condensation
   band is nine letters long; a letter inside it holds fractional opacity and blur from a
   smoothstep ramp recomputed per frame, so no unit of text ever resolves as a block, not a
   word, not even a letter. On settle the front runs one band past the last letter, because a
   letter only finishes once the front is a whole band beyond it.

3. **The mist is one element for the whole lifecycle.** Before the first word it breathes where
   the text will start (the breath, replacing the dots, still labelled "Thinking"). When the
   reply speaks it glides along the front, positioned each frame from the frontmost letter's
   offsets with its own easing, so a line wrap is a curve rather than a teleport, and it is
   clamped inside the bubble's box so the blob hugs an edge rather than leaving it. When the
   reply settles it evaporates where the last word ends. It is the streaming bubble's **only**
   colour: the block caret, the three dots and the in-progress glow are deleted, which makes
   the colour rule stricter than the design doc used to ask (colour sits exactly where the work
   is, nowhere else on the bubble).

4. **The text lays out once; the painted box tracks the front.** The letter DOM is laid at the
   bubble's final wrap width the moment the bubble mounts (the 82% cap resolved against the
   log's content box, exactly as `max-width` resolved it), so letter positions never change
   after they are laid. The bubble's own box is posed by the clock in every phase: a small pill
   drawn around the mist while breathing (which is what keeps the out-of-flow mist from
   collapsing the empty bubble), then width and height eased every frame toward where the front
   actually is, then settled with the last letter. The box's edge doubles as the reveal
   (`overflow: hidden` clips only letters that have not condensed), and a wrap becomes a curve
   the box rounds. This is the panel's replayed-height doctrine (ADR-0033: `auto` to `auto`
   cannot transition) applied one level down.

5. **A partial trailing word is held out of the reveal.** While the turn streams, the front's
   goal is the letters up to the last completed word (a word is completed by the whitespace
   after it); the trailing fragment's letters stay at opacity zero. A fragment that grows can
   still re-wrap to the next line, but only invisible letters ever move, so the reveal never
   jumps lines. The drain releases the hold, so the reply's last word (which no whitespace ever
   completes) condenses when the turn ends.

6. **Words are unbreakable boxes, and a giant token is chunked to keep the wrap-inside rule.**
   Letters sit in per-word `white-space: pre` inline blocks so a word never breaks mid-glide,
   which would defeat `overflow-wrap: anywhere` for a 64-character hash and grow the horizontal
   bar the scrollbar rules forbid. So a run of non-whitespace longer than 24 letters is split
   into 24-letter boxes: the bubble can break between them, mid-token, which is the same lesser
   evil the raw bubble already chose. Whitespace between boxes is plain text nodes, so newlines
   and spaces render exactly as `pre-wrap` always rendered them.

7. **The reducer is untouched; the bubble owns its presentation state.** `turnState` still only
   appends words to `Message.content`. `components/WhisperBubble.tsx` latches whether the
   message was streaming when it mounted: a settled message from history renders as one plain
   text node with none of the machinery, and a message this instance streamed keeps its letter
   DOM after settling so nothing re-wraps or re-kerns under the reader. The clock
   (`whisper/useWhisperClock.ts`) is a rAF loop in the mark's own shape that writes letter
   ramps, the mist transform and the box pose imperatively; its only `setState` is the two
   phase transitions (breath to talking, talking to settled), never per frame, which is the
   lesson ADR-0036 recorded about rAF clocks beside React. The bubble reports growth through an
   `onGrow` callback wired to the history's tail pin, so the drain that outlives the last
   render cannot slide the tail out from under a pinned reader.

8. **Reduced motion schedules no frames at all**, the mark's standard. The stylesheet reveals
   letters at full opacity as they arrive, the mist holds a still pose (the global
   reduced-motion rule already collapses its breathing), and a CSS floor holds the breath pill
   so the unposed bubble cannot collapse around the mist.

9. **The letter DOM is presentation, not the accessible text.** The word boxes are
   `aria-hidden` behind a visually hidden copy of the full content, so assistive tech reads the
   reply as text rather than as hundreds of one-letter spans; the mist carries the "Thinking"
   label during the breath, where the dots used to.

## Consequences

- New: `whisper/front.ts` (pure engine and tokenizer), `whisper/useWhisperClock.ts` (the frame
  clock), `components/WhisperBubble.tsx`, each with its own test file; `Message.tsx` hands
  assistant bubbles to `WhisperBubble` and renders user bubbles as plain text. Deleted from
  `overlay.css`: `.thinking`, `.caret`, `.w`, the `wordin` keyframes and the `.b-ai.streaming`
  glow; every bubble now enters with one soft whole-bubble fade (`bubblein`) instead of per-word
  rises, replacing a history load that animated every word of every bubble.
- Streaming costs one layout read per frame (the front letter's offsets) plus style writes
  bounded to the band's dozen letters; letter collection re-queries only when the letter count
  changes. Measured in the browser validation for this slice, headless Chromium at 660x760
  sampling every frame of a whole demo stream (breath, reasoning burst, condensation, drain):
  540 frames, 16.7ms median, 16.8ms worst, which is the same answer the mark's own measurement
  gave in ADR-0031, so nothing comes close to missing the budget.
- The browser validation also caught one defect before it shipped, recorded here so the class
  rule is not relearned: the whisper bubble is `box-sizing: border-box` (the clock's arithmetic
  is over the box it can see), which silently re-scoped `.bubble`'s `max-width: 82%` to the
  border box, a box two paddings narrower than the text was laid for, and the overflow clip ate
  exactly that much of every full line. `.whisper` therefore carries `max-width: none`: the
  clock's measured cap IS the 82%, resolved the way the content-box rule resolved it.
- Kerning pairs inside a word are lost to the per-letter boxes while a streamed message is on
  screen. Invisible at 13.5px in the system stack (checked by eye in both themes); a serif-ish
  fallback stack would want a look before anyone changes the font, recorded as a refinement.
- The wrap width is measured once per streamed bubble, so a window resized mid-stream keeps the
  old wrap until the next message; the v1 body window is fixed-size, so only the browser dev
  flow can see it. Recorded as a refinement.
- The drain can grow the bubble a few pixels after the turn's last render; the history's
  min-height floor hides it from the panel's measured moves today, and the tail pin rides
  `onGrow`. The panel learning about between-render growth is recorded as a refinement.

## Addendum (2026-07-21): three fixes from the first live look

The maintainer called two defects on the landed effect and his screenshot surfaced a third; all
three landed in the slice that followed, with the mechanisms recorded so they are not
relearned.

1. **Letters are inline, never inline-block.** An inline-block letter is its own little box,
   and the engine lays boxes on whole pixels, so every letter's advance was rounded and a
   reply read as a ransom note, worst under Windows display scaling. Inline spans keep the
   text's own sub-pixel advances, and opacity and blur are both fine on inline boxes. Kerning
   pairs across letter boundaries stay lost either way (element boundaries split shaping
   runs), so the licensed-face refinement stands unchanged.

2. **The bubble announces its growth in the panel's own roll contract.** The panel replays its
   geometry from a measurement taken at the last render (ADR-0033), which assumed content only
   changes at renders; the whisper grows the bubble between them, so every token replayed the
   panel from a stale height. Traced in headless Chromium at 660x1000 through one reply past
   the chat floor: eight backward snaps of the top edge, up to 6.6px. The bubble now carries
   `data-morphing` (holding the height it is easing to) from its first spoken letter to its
   settle and dispatches the contract's start and end events (`overlay/morph.ts`), so
   placements defer, the panel's auto height follows the box frame by frame, and the bottom
   edge rides along when a landing line meets the ceiling. Re-traced after: zero reversals,
   zero backward snaps. This also lands the "drain growth the panel's measured moves never
   see" refinement filed above: deferral is exactly the panel hearing between-render growth,
   and the end event is its re-measure.

3. **The settle waits for the mist.** The drain sprints the front while the mist trails on its
   own ease, and stopping the clock the instant the last letter cleared froze the glide
   mid-line: the evaporation played a dozen letters short of the reply's end (the user's
   screenshot has the smudge). The clock now runs a coda of a few frames until the blob is
   within a pixel of the last word, then settles, so the reply ends where it says it does.

## Addendum (2026-08-07): the roll publishes the height the box stands on

Decision 2 of the addendum above gave the bubble the panel's roll contract, and the value it
published was `String(Math.round(tH))` while the box beside it was written with
`${s.h.toFixed(1)}px`. Two roundings of one number, on a contract whose whole purpose is that both
sides agree. Filed as a refinement rather than fixed on sight, because a bubble is never handed back
to its own layout the way a section is and the step that made the section's case might not exist
here at all.

Traced first, at 900x1000 in headless Chromium over the demo. It does not exist: across 172 frames
inside one reply's roll there is no frame where the panel's height moves and the bubble's does not,
and the panel never animates its own height during a reply, so the prediction is computed once per
wrap and thrown away. What the trace found instead is that the published number is not only a
prediction. On a summon landing inside the roll it is the edge the panel pins itself to, and the
rounding put the panel on 316.59375px where the height the roll leaves it at centres on
316.34375px, an edge it then kept for the session. The mismatch was exactly half a pixel on all five
of the reply's wraps, `offsetTop` being whole and the line box 22.475px.

The clock now publishes `tH.toFixed(1)`, the rounding the box itself is written with, so the panel
predicts from the number the bubble will stand on. The full trace, the falsification of the
instrument and the mutation proof are in
[ADR-0035](ADR-0035-console-and-motion.md), which owns the roll contract and the panel's
measurement work; the entry that demanded the measurement first is in
[refinements/index.md#body-overlay](../refinements/index.md#body-overlay).

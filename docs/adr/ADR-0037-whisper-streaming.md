# ADR-0037: The reply whispers in, and the bubble grows at its pace

**Status:** Accepted (2026-08-18)

## Context

The maintainer judged the earlier thinking and streaming effect out of the overlay's design
language, on four counts. The caret was a pulsing block cursor, terminal chrome in a language that
says bubbly and never sharp. The pre-token shimmer was three bobbing dots, every messenger's typing
indicator, in a product whose own thinking signal is the mark. The lifecycle was three states glued
by hard swaps (dots vanish and words begin; the caret vanishes when the turn ends) in an overlay
where the sun morphs into the moon. And the per-word rise plus blur was the stock reveal of recent
AI apps, with none of the overlay's own motifs. The design doc prescribed that effect, so this
ADR revises [overlay-ux.md](../design/overlay-ux.md) §1, §2 and §4 with it.

The replacement was chosen over three rounds of live demonstrations, each streaming real replies on
the overlay's own tokens. Round one named a family of four voices on the line "the mark thinks, the
window dreams, the reply speaks" (Murmur, Whisper, Patter, Intone, each a breath, words and settle
sequence whose breath element morphs into the leading edge). The maintainer chose **Whisper**: the
reply condenses like breath on glass, words resolving from a blur behind a small accent mist, with
no caret, no ring and no glow. The choice was first misread as Murmur, because the maintainer named
the tile by position and the page had stacked its grid to one column; the row was restored so the
choice could be made again by eye, and a choice is confirmed by look, not by label. Round two
smoothed Whisper's one flaw (whole words arriving in the mist as blocks) four ways, and the
maintainer chose **Fog**: the mist survives the breath and glides along the condensation front as
its source.
Round three fixed two defects with one cause, the bubble's box being raw layout: the out-of-flow
mist let the empty waiting bubble shrink-wrap to a sliver behind it, and arriving words took layout
space the instant they arrived, so the box lurched by words and whole lines ahead of anything
visible.

## Decision

1. **The reply's streaming effect is Whisper, one voice, not a registry.** The names used during
   the demonstration (the Voice family, and Fog against Hush, Dew and Sigh) were working labels and
   go with the tiles that lost; what ships is the overlay's streaming effect, and no storage key is
   frozen because nothing is stored. Making the voice a chosen style beside the theme, the iris and
   the dream (the Face's fourth row) is
   [task 158](../refinements/tasks/158-voice-as-picked-row.md), which is possible because the
   effect sits behind one component boundary.

2. **Letters condense on a continuous front, paced not timed.** The engine
   (`body/app/src/whisper/front.ts`, pure) holds one fractional position moving at one velocity. The
   velocity eases toward what the backlog warrants (the backlog over `CATCHUP_SECONDS`, 0.35 s,
   clamped to 20..150 letters per second) and is never reset, so arrivals only move the target: the
   panel's own motion rule (paced not timed, resumed not restarted) applied per letter. The
   condensation band is nine letters long; a letter inside it holds fractional opacity and blur
   from a smoothstep ramp recomputed per frame, so no unit of text ever resolves as a block, not a
   word, not even a letter. On settle the front runs one band past the last letter, because a
   letter only finishes once the front is a whole band beyond it.

3. **The mist is one element for the whole lifecycle.** Before the first word it breathes where the
   text will start (the breath, replacing the dots, still labelled "Thinking"). When the reply
   speaks it glides along the front, positioned each frame from the frontmost letter's offsets with
   its own easing, so a line wrap is a curve rather than a teleport, and it is clamped inside the
   bubble's box. When the reply settles it evaporates where the last word ends: the drain runs the
   front out quickly while the mist follows on its own ease, so the clock runs a short extra period
   until the mist is within a pixel of the last word and only then settles, since stopping at the
   last letter froze the glide a dozen letters short. The mist is the streaming bubble's **only**
   colour: the block caret, the three dots and the in-progress glow are deleted, so colour sits
   exactly where the work is and nowhere else on the bubble.

4. **The text lays out at a measured width; the painted box tracks the front.** The letter DOM is
   laid at the bubble's final wrap width (the 82% cap resolved against the log's content box, as
   `max-width` resolves it), and letter positions hold for as long as that width does, so no wrap
   happens under a running reveal. The bubble is `box-sizing: border-box`, because the clock's
   arithmetic is over the box it measures, so `.whisper` sets `max-width: none`: a border-box
   `max-width: 82%` would be two paddings narrower than the text was laid for and the clip would
   cut that much off every full line. The box is posed by the clock in every phase: a small pill
   around the mist while breathing (which keeps the out-of-flow mist from collapsing the empty
   bubble), then width and height eased every frame toward where the front is, then settled with
   the last letter. The box's edge doubles as the reveal (`overflow: hidden` clips only letters
   that have not condensed), and a wrap becomes a curve the box rounds. This is the panel's
   replayed-height rule ([ADR-0033](ADR-0033-panel-growth.md): `auto` to `auto` cannot transition)
   applied one level down. The measurement and the box arithmetic live in `whisper/metrics.ts`
   (`measure`, `boxFor`), so a frame and a re-lay pose from one function.

5. **A partial trailing word is held out of the reveal.** While the turn streams, the front's goal
   is the letters up to the last completed word (a word is completed by the whitespace after it);
   the trailing fragment's letters stay at opacity zero. A fragment that grows can still re-wrap to
   the next line, but only invisible letters ever move, so the reveal never jumps lines. The drain
   releases the hold, so the reply's last word (which no whitespace completes) condenses when the
   turn ends.

6. **Words are unbreakable boxes, letters are inline, and a giant token is chunked.** Letters sit in
   per-word `white-space: pre` inline blocks so a word never breaks mid-glide. The letters
   themselves are inline spans, never inline-block: an inline-block letter is its own box, laid on
   whole pixels, so every advance was rounded and a reply read as a ransom note, worst under
   Windows display scaling, while inline spans keep the text's sub-pixel advances and take opacity
   and blur as well. A per-word box would defeat `overflow-wrap: anywhere` for a 64-character hash
   and grow the horizontal bar the scrollbar rules forbid, so a run of non-whitespace longer than
   `CHUNK_LETTERS` (24) is split into 24-letter boxes the bubble can break between, the tradeoff the
   raw bubble already made. Whitespace between boxes is plain text nodes, so newlines and spaces
   render as `pre-wrap` rendered them.

7. **The reducer is untouched; the bubble owns its presentation state.** `turnState` still only
   appends words to `Message.content`. `components/WhisperBubble.tsx` latches whether the message
   was streaming when it mounted: a settled message from history renders as one plain text node with
   none of the machinery, and a message this instance streamed keeps its letter DOM after settling
   so nothing re-kerns under the reader. The clock (`whisper/useWhisperClock.ts`) is a rAF loop in
   the mark's own shape that writes letter ramps, the mist transform and the box pose imperatively;
   its only `setState` is the two phase transitions (breath to talking, talking to settled), never
   per frame, so the frame loop never re-renders the bubble. The bubble reports growth through an
   `onGrow` callback wired to whatever keeps the history at its tail, so growth that outlives the
   last render cannot slide the tail out from under a reader who was at the end.

8. **Reduced motion schedules no frames at all**, the mark's standard. The stylesheet reveals
   letters at full opacity as they arrive, the mist holds a still pose (the global reduced-motion
   rule already collapses its breathing), and a CSS minimum size keeps the breath pill open so the
   unposed bubble cannot collapse around the mist.

9. **The letter DOM is presentation, not the accessible text.** The word boxes are `aria-hidden`
   behind a visually hidden copy of the full content, so assistive tech reads the reply as text
   rather than as hundreds of one-letter spans; the mist holds the "Thinking" label during the
   breath, where the dots used to.

10. **The bubble announces its growth in the panel's roll contract.** The panel replays its geometry
    from a measurement taken at the last render, and the whisper grows the bubble between renders,
    so without this every token replayed the panel from a stale height and snapped its top edge
    backwards. The bubble sets `data-morphing` (the height it is easing to) from its first spoken
    letter to its settle and dispatches the contract's start and end events (`overlay/morph.ts`), so
    placements wait, the panel's auto height follows the box frame by frame, and the end event is
    the re-measure after the drain. The published height is `tH.toFixed(1)`, the rounding the box
    itself is written with, because a summon arriving inside the roll fixes the panel on that
    number ([ADR-0035](ADR-0035-console-and-motion.md) decision 33).

11. **A window resize re-lays every once-streamed bubble.** Every such bubble keeps its letter DOM
    and the px box the clock left it on, so without a re-lay a resized window left the whole
    conversation laid for a width that no longer existed, overhanging the log and clipped by the
    history's `overflow-x: clip`. `watchWrap` listens for the window's own `resize`, the idiom
    `overlay/usePanelMotion.ts` places the panel on, which is complete for as long as the panel's
    width stays viewport-derived (`.panel` is `min(560px, 92vw)`; the day it is not is
    [task 311](../refinements/tasks/311-wrap-width-trigger-completeness.md)). A `ResizeObserver` on
    the log was rejected: the log's height follows the posed bubble every frame, so it would fire
    per frame, and writing the letter DOM's width inside an observation of an ancestor raises the
    "loop completed with undelivered notifications" error `overlay/panelWatch.ts` has already
    met. A bubble whose loop has stopped re-poses at once from the last letter's fresh offsets and
    the same `boxFor`, rather than restarting the loop, which would trail the drag and replay the
    phase transitions and the roll for a reply that ended long ago; it reports the new size
    through `onGrow`. The mist is not re-posed, having evaporated to opacity zero (`mistgone` runs
    `forwards`).

## Consequences

- The whisper lives in `whisper/front.ts` (pure engine and tokenizer), `whisper/metrics.ts`,
  `whisper/useWhisperClock.ts` and `components/WhisperBubble.tsx`, each tested; `Message.tsx`
  hands assistant bubbles to `WhisperBubble` and renders user bubbles as plain text. Every bubble
  enters with one soft whole-bubble fade (`bubblein`) instead of per-word rises.
- Streaming costs one layout read per frame (the front letter's offsets) plus style writes bounded
  to the band's dozen letters; letter collection re-queries only when the letter count changes.
  Sampled over a whole demo stream, every frame finished inside its refresh interval, as the
  mark's own measurement did ([ADR-0031](ADR-0031-bubble-mark.md)); the measurements are in
  [panel motion](../readings/panel-motion.md#the-whisper-bubble).
- Kerning pairs across letter boundaries are lost while a streamed message is on screen, because
  element boundaries split shaping runs. Invisible at 13.5px in the system stack, checked by eye in
  both themes; a different font stack needs checking first
  ([task 162](../refinements/tasks/162-per-letter-kerning-pairs.md)).
- jsdom has no layout, so a re-wrap, the roll's frames and the per-frame cost are validated in
  headless Chromium. A listener that throws is reported to the window rather than to whoever
  dispatched the event, so a test that dispatches a resize and asserts on the DOM cannot see the
  throw; the resize tests listen for `error` on the window across the dispatch.

## Alternatives rejected

- **A registry of voices now** (decision 1), and the three losing voices and the three Fog rivals.
- **A caret, typing dots or a glow**, and the per-word rise plus blur (Context).
- **Inline-block letters** (decision 6) and a **`ResizeObserver` on the log** (decision 11).
- **Restarting the clock on a resize** (decision 11).

## Related

- Design: [overlay-ux.md](../design/overlay-ux.md). Module contract:
  [body-app.md](../modules/body-app.md). Measurements:
  [panel motion](../readings/panel-motion.md).
- [ADR-0033](ADR-0033-panel-growth.md) and [ADR-0035](ADR-0035-console-and-motion.md) (the panel's
  motion and the roll contract), [ADR-0031](ADR-0031-bubble-mark.md) and
  [ADR-0036](ADR-0036-window-edge.md) (the mark's and the window's clocks).

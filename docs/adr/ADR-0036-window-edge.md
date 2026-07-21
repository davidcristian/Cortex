# ADR-0036: The window's dreaming edge, as a picked style

Date: 2026-07-21. Status: accepted.

## Context

The maintainer asked for the window to go "cloud-like, dreamy around the corners" and picked, from a
live artifact pitch of five treatments, the liquid one: the panel's silhouette warped by the same
kind of maths that animates the bubble mark. Pushed further over two more rounds, the winner was a
family rather than one setting, and the maintainer chose to ship all of it as choices, including the
crisp edge as a choice of its own, with the plain liquid as the default. The pitch also surfaced
two implementation facts this ADR records so they are not relearned: Chromium does not clip
backdrop-filter output by a `path()` clip, and text must never sit on a layer whose clip is
re-rasterized every frame or it goes soft.

## Decision

1. **A third appearance registry: the window.** `edge/edges.ts` mirrors `theme/themes.ts` and
   `mark/marks.ts`: an `EdgeStyle` is a named set of numbers (spectrum, weights, glow), `EDGES`
   is the registry, `resolveEdge(preference)` falls back to the default, and a fifth style is a
   literal with no other code change. The persisted key is `overlay.window` in the preference
   record (ADR-0032).

2. **Four ship, named as a ladder of dream depth: Still, Lucid, Reverie, Trance.** The names are
   a designed set under the naming language recorded in ADR-0031's 2026-07-21 addendum: one word
   each, one metaphor for the family, and the family's order IS the information, so the tile row
   explains intensity without a caption. Still is today's crisp glass as a real choice, not an
   off switch. Storage keys are the lowercase labels, right from day one.

3. **Lucid is the default**, by the user's explicit call: a fresh overlay breathes. `resolveEdge`
   with no or an unknown preference lands there, exactly as `resolveMark` lands on its default.

4. **The liquid is the mark's maths on the window's perimeter.** `edge/liquid.ts` samples the
   panel's rounded rectangle as a closed loop and displaces each point along its normal by a sum
   of sine waves whose spatial orders are all integers of two or higher, corner-weighted with a
   share left to the straight runs. Integer orders are what close the loop without a seam and
   hold the shape's centre, the same invariant the mark's registry tests pin; only the time
   speeds are aperiodic, so the motion never visibly repeats. One path string is computed per
   frame and reused by the clip, the hairline and the glow strokes.

5. **The liquid lives inside the panel's layout box.** The neutral outline is inset by the
   style's worst-case reach, so displacement can never cross the border box. The panel's
   geometry, growth and travel machinery (ADR-0033, ADR-0034, ADR-0035) is untouched: `overflow:
   hidden` keeps the growth reveal, the box-shadow stays the panel's own (the few px between the
   glass line and the layout box vanish inside a 90px blur), and `usePanelMotion` never learns
   the edge exists.

6. **The words never ride the warping layer.** The animated clip is applied to a background-only
   glass slab under the content; the content column sits above it, un-clipped and never
   re-rasterized by the animation, which is what keeps the type exactly as sharp as today's. The
   blurred glow strokes paint in an svg *between* slab and content, so nothing soft can cross a
   glyph, and only the crisp one-px hairline rides above the content, where no text ever reaches.

7. **Live styles trade the backdrop blur for a hair more opacity.** Measured in the pitch:
   Chromium composites `backdrop-filter` output un-clipped by a `path()` clip, a sharp frosted
   rectangle ghosting behind the sculpted edge. So a live edge paints `--panel-solid`, a new
   per-theme token, instead of glass-over-blur. In the v1 window the ground behind the panel is
   opaque (design/overlay-ux.md §4), so nothing is visibly lost today; the trade is refiled with
   the transparent-window pass in `docs/refinements/body-overlay.md`.

8. **The glow is the send button's trick, and Trance is the one written exception.** A smolder is
   two strokes riding the outline, cross-faded by CSS opacity (gradients cannot interpolate):
   Reverie's is neutral at rest and takes the accent while a turn runs, which keeps §1 of the
   design doc intact; Trance keeps a low accent ember lit at rest, the single sanctioned breach
   of "color is activity", chosen by the user with its cost written into the design doc.

9. **Working depth eases, stillness is exact.** The edge deepens toward a working pose while
   `isTurnActive` and eases back after, via a pure exponential approach advanced on the mark's
   own frame clock (`useMarkClock`). Reduced motion schedules no frames, holds the mark's still
   pose and snaps the depth, so a still edge is genuinely still.

## Consequences

- New: `edge/liquid.ts` (pure geometry + the depth approach), `edge/edges.ts` (the registry),
  `components/PanelEdge.tsx` (slab, glow, hairline), `components/EdgeMini.tsx` (the tile art).
  Changed: `Panel` mounts the edge and flags `edge-live`/`edge-working`, `AppearanceTab` gains
  the Window swatch row, `usePreferences` the `overlay.window` key, `themes.ts` the
  `panelSolid` token, `overlay.css` the edge layer rules.
- The appearance tab grows a third row, which puts it past the console's shared-height spread;
  the tab stack's existing judgement (`TAB_SPREAD_PX`) handles that by design, no new motion.
- Per-frame cost is one more path-string layer of the kind ADR-0031 already measured well inside
  the frame budget; the panel's content does not re-render with it.
- The mini tiles draw each style's color signature (Reverie's smolder, Trance's ember) even at
  rest, because four liquids that differ mostly by glow must be tellable apart in a swatch row;
  the note under the row says when the color actually appears.

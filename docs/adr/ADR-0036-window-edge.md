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

5. **The liquid rides the window's own edge, on a bleed.** The edge layers extend a fixed bleed
   past the panel's border box (`liquid.ts` owns the number and the wrapper wears it as an
   inline inset, so the two cannot drift), the neutral outline sits exactly on the panel's edge,
   and every style's worst-case reach is pinned under the bleed by the registry tests, so the
   waves swing around the regular border, outward into the bleed and inward over the glass,
   without ever leaving the wrapper. The panel's geometry, growth and travel machinery
   (ADR-0033, ADR-0034, ADR-0035) still never learns the edge exists; what moves is the clip: a
   liquid panel goes `overflow: visible` and hands the content clip to the views box (same box,
   same radius), which keeps the growth reveal. The shadow moves too: cast from the border box
   it traced the original rectangle behind the liquid (worst on the light ground, where the
   maintainer read it as the old border still standing), so a liquid panel drops its box-shadow and
   the edge wrapper carries a `drop-shadow` filter instead, which falls from the clipped
   silhouette itself, frame by frame; the glow svgs overflow visibly for the same reason, or
   their blur seams at the wrapper's rectangle. The first cut inset the whole liquid by the
   reach instead, to spare even the clip a change, and the maintainer caught it on sight: it read as
   a window that had shrunk.

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

## Addendum (2026-07-21): the Dream tiles are portraits

The first tile art drew the real liquid at about a third of its size, and the maintainer called the
row ugly, with reason: honesty at that scale shrinks the bleed into dead margin and the waves
into a nervous line, and a wall of empty wireframes sat under two rows of real pictures. Three
directions were pitched live (a portrait, a near-full-size corner crop, an aura around a still
core) and the maintainer chose the portrait: each tile is the same miniature window the theme tiles
draw, its outline gone liquid, the amplitude chosen for the swatch rather than inherited from
the panel. The geometry module grew `loopPath`, the sampler on an explicit frame, and the
panel's `edgePath` became its uniform-inset wrapper, so the tile and the window share one
sampler and re-tune only the frame.

One tile moves differently on purpose. Frozen in its accent, Reverie read as "a lighter Trance"
(the maintainer's words), when the style IS the change: neutral at rest, accent while a turn runs.
Its tile cross-fades two glow strokes on a slow cycle, and the phase is chosen so the frozen
reduced-motion pose lands exactly mid-blend, both truths at once. Trance stays constantly lit,
which is precisely the difference between the two styles, now visible in the row.

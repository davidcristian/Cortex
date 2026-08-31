# ADR-0036: The window's dreaming edge, as a chosen style

**Status:** Accepted (2026-07-21)

## Context

The maintainer asked for the window to go "cloud-like, dreamy around the corners" and chose, from a
live demonstration of five treatments, the liquid one: the panel's silhouette warped by the same
kind of maths that animates the bubble mark. Pushed further over two more rounds, the result was a
family rather than one setting, and the maintainer chose to ship all of it as choices, including the
crisp edge as a choice of its own, with the plain liquid as the default. The demonstration also
turned up two implementation facts this ADR records so they are not relearned: Chromium does not
clip backdrop-filter output by a `path()` clip, and text must never sit on a layer whose clip is
re-rasterized every frame, or it goes soft.

## Decision

1. **A third appearance registry: the window.** `edge/edges.ts` mirrors `theme/themes.ts` and
   `mark/marks.ts`: an `EdgeStyle` is a named set of numbers (spectrum, weights, glow), `EDGES`
   is the registry, `resolveEdge(preference)` falls back to the default, and a fifth style is a
   literal with no other code change. The persisted key is `overlay.window` in the preference
   record (ADR-0032).

2. **Four ship, named as increasing depths of dream: Still, Lucid, Reverie, Trance.** The names
   are a designed set under the naming language recorded in ADR-0031 decision 7: one word each, one
   metaphor for the family, and the family's order IS the information, so the tile row explains
   intensity without a caption. Still is today's crisp glass as a real choice, not an off switch.
   Storage keys are the lowercase labels, right from day one.

3. **Lucid is the default**, by the user's explicit choice: a fresh overlay breathes. `resolveEdge`
   with no preference, or an unknown one, returns it, exactly as `resolveMark` returns its own
   default.

4. **The liquid is the mark's maths on the window's perimeter.** `edge/liquid.ts` samples the
   panel's rounded rectangle as a closed loop and displaces each point along its normal by a sum
   of sine waves whose spatial orders are all integers of two or higher, weighted toward the
   corners with a share left to the straight runs. Integer orders are what close the loop without a
   join and keep the shape's centre, the same invariant the mark's registry tests assert; only the
   time speeds are aperiodic, so the motion never visibly repeats. One path string is computed per
   frame and reused by the clip, the hairline and the glow strokes.

5. **The liquid follows the window's own edge, on a bleed.** The edge layers extend a fixed bleed
   past the panel's border box (`liquid.ts` owns the number and the wrapper applies it as an
   inline inset, so the two cannot disagree), the neutral outline sits exactly on the panel's edge,
   and the registry tests assert that every style's worst-case reach stays under the bleed, so the
   waves swing around the regular border, outward into the bleed and inward over the glass,
   without ever leaving the wrapper. The panel's geometry, growth and travel machinery
   (ADR-0033, ADR-0034, ADR-0035) is untouched by the edge; what moves is the clip: a
   liquid panel goes `overflow: visible` and hands the content clip to the views box (same box,
   same radius), which keeps the growth reveal. The shadow moves too: cast from the border box
   it traced the original rectangle behind the liquid (worst on the light ground, where the
   maintainer read it as the old border still there), so a liquid panel drops its box-shadow and
   the edge wrapper uses a `drop-shadow` filter instead, which falls from the clipped
   silhouette itself, frame by frame; the glow svgs overflow visibly for the same reason, or
   their blur shows a join at the wrapper's rectangle. The first version inset the whole liquid by
   the reach instead, to spare even the clip a change, and the maintainer saw it at once: it read
   as a window that had shrunk.

6. **The words never sit on the warping layer.** The animated clip is applied to a background-only
   glass slab under the content; the content column sits above it, un-clipped and never
   re-rasterized by the animation, which is what keeps the type exactly as sharp as before. The
   blurred glow strokes paint in an svg *between* slab and content, so nothing soft can cross a
   glyph, and only the crisp one-px hairline sits above the content, where no text ever reaches.

7. **Live styles trade the backdrop blur for slightly more opacity.** Measured during the
   demonstration: Chromium composites `backdrop-filter` output without clipping it by a `path()`
   clip, leaving a sharp frosted rectangle behind the sculpted edge. So a live edge paints
   `--panel-solid`, a new per-theme token, instead of glass over blur. In the v1 window the ground
   behind the panel is opaque (design/overlay-ux.md §4), so nothing is visibly lost today; the
   trade-off is recorded again with the transparent-window work
   ([R-157](../refinements/tasks/157-liquid-edge-backdrop-blur.md)).

8. **The glow reuses the send button's technique, and Trance is the one written exception.** A
   smolder is two strokes along the outline, cross-faded by CSS opacity (gradients cannot
   interpolate): Reverie's is neutral at rest and takes the accent while a turn runs, which keeps §1
   of the design doc intact; Trance keeps a low accent ember lit at rest, the single allowed
   exception to "color is activity", chosen by the user with its cost written into the design doc.

9. **Working depth eases, stillness is exact.** The edge deepens toward a working pose while
   `isTurnActive` and eases back after, through a pure exponential approach advanced on the mark's
   own frame clock (`useMarkClock`). Reduced motion schedules no frames, holds the mark's still
   pose and sets the depth at once, so a still edge is really still.

10. **The Dream tiles are portraits.** Each tile in the console's Dream row
    (`components/EdgeMini.tsx`) is the same miniature window the theme tiles draw, its outline gone
    liquid, with the amplitude chosen for the swatch rather than inherited from the panel. Drawing
    the real liquid at true scale shrank the bleed into dead margin and the waves into a jittery
    line, and the maintainer rejected that row. `loopPath` in `edge/liquid.ts` samples the loop on
    an explicit frame, and the panel's `edgePath` is its uniform-inset wrapper, so the tile and the
    window share one sampler and change only the frame. The tiles draw no ground of their own: a
    painted desktop under the little window put a second surface inside the card, and only the
    theme row draws one, because there the ground is the thing being chosen. Reverie's tile
    cross-fades its two glow strokes on a slow cycle whose phase puts the frozen reduced-motion pose
    exactly mid-blend, because frozen in its accent it read as a lighter Trance when the style is
    the change between neutral and accent; Trance's tile stays lit, which is the difference between
    the two.

11. **The preview card always dreams, in Lucid.** The completed-while-minimized preview
    (`components/Preview.tsx`) mounts a `PanelEdge` of its own, fixed to `LUCID` rather than to
    the user's choice, and gives it the whole surface the way `.panel.edge-live` does: no border, no
    fill, no box-shadow, `overflow: visible`, and the content lifted a layer so it paints above the
    glass. The card is the one thing that arrives on its own, over whatever the user is working
    in, so a soft edge is what keeps it from reading as a system notification. The two louder
    styles use colour, and on a card whose message is that a turn has *finished* an accent rim
    would announce activity, which §1 of the design doc reserves colour for; Still would leave the
    preview the only hard-edged surface in an overlay whose window breathes. The card needs no
    content clip: it is four clamped lines inside its own padding, so nothing reaches the edge.

## Consequences

- New: `edge/liquid.ts` (pure geometry and the depth approach), `edge/edges.ts` (the registry),
  `components/PanelEdge.tsx` (slab, glow, hairline), `components/EdgeMini.tsx` (the tile art).
  Changed: `Panel` mounts the edge and flags `edge-live`/`edge-working`, `AppearanceTab` gains
  the Dream swatch row, `usePreferences` the `overlay.window` key, `themes.ts` the
  `panelSolid` token, `overlay.css` the edge layer rules.
- The appearance tab grows a third row, which puts it past the console's shared-height spread;
  the tab stack's existing allowance (`TAB_SPREAD_PX`) covers that by design, no new motion.
- Per-frame cost is one more path-string layer of the kind ADR-0031 already measured well inside
  the frame budget; the panel's content does not re-render with it.
- The mini tiles draw each style's colour (Reverie's smolder, Trance's ember) even at rest,
  because four liquids that differ mostly by glow must be distinguishable in a swatch row; the
  note under the row says when the colour actually appears.

## Alternatives rejected

- **Insetting the whole liquid by its reach** to spare the clip a change: it read as a window that
  had shrunk (decision 5).
- **Keeping the backdrop blur on a live edge**: Chromium does not clip its output by a `path()`
  clip (decision 7).
- **Tile art drawn at true scale**, or on a painted ground (decision 10).

## Related

- Code: `body/app/src/edge/edges.ts`, `edge/liquid.ts`, `components/PanelEdge.tsx`,
  `components/EdgeMini.tsx`, `components/Preview.tsx`, `overlay.css`.
- Design: [overlay-ux.md](../design/overlay-ux.md) §2.
- ADRs: [ADR-0031](ADR-0031-bubble-mark.md) (the mark's maths and the naming standard),
  [ADR-0032](ADR-0032-preference-record.md) (the preference record),
  [ADR-0035](ADR-0035-console-and-motion.md) (the console that holds the Dream row).

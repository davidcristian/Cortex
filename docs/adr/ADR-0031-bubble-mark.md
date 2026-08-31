# ADR-0031: The bubble mark, and the mark as a picked style

**Status:** Accepted (2026-07-21)

## Context

The overlay's activity mark (the corner orb while a turn runs, and the panel's empty state) used to
be the **living rings**: two sine-modulated wavy bands stroked with the eight-hue gradient, spinning
as one under a CSS `spin` and `huedrift` pair while each band's wave depth pulsed on its own SMIL
clock.

Two things replaced it.

1. **It looks like someone else's mark.** Concentric coloured rings turning around a point is close
   enough to a widely shipped assistant identity that the resemblance is the first thing a viewer
   mentions. For a personal product whose whole visual argument is "this is mine", that is a defect
   in the mark regardless of how it animates.
2. **The maintainer asked for a soap bubble instead**: an actual bubble, not a perfect circle, sheen
   and all, warping along its radius.

Four candidate bubbles were designed and reviewed as running animations at real size. The user liked
all four, which turned a one-of-four choice into the decision below.

## Decision

1. **The mark is a soap bubble, and its geometry is sine harmonics of order two or higher.** A
   lobe is a circle whose radius is modulated by a sum of harmonics, `r(θ) = R·(1 + Σ aᵢ·sin(nᵢθ +
   φᵢ(t)))`, each harmonic travelling at its own period. Because every `nᵢ ≥ 2`, the mean of the
   outline over a revolution is exactly the center, so **the centroid and the mean radius cannot
   move**, and the design rule "no breathing scale, no positional drift, the anchor holds rock
   still" ([overlay-ux.md](../design/overlay-ux.md)) follows from the maths rather than from a
   convention someone has to remember. An `n = 1` term would move the whole shape; that is the one
   number the tests check (`marks.test.ts`, "uses only harmonics of order two or higher").

2. **Four styles ship, as a plug-and-play registry, defaulting to Mull.** `mark/marks.ts` is the
   deliberate twin of `theme/themes.ts`: a `MarkStyle` is a named set of numbers, `MARKS` is the
   registry, `resolveMark(preference)` falls back to the default, and adding a fifth style is a
   literal in that file and no other code change. The four are **Mull** (two slow modes roll the
   outline over, settling on nothing; the default), **Muse** (near circular, a calm surface with
   the film drifting beneath it), **Hunch** (still, then a ripple strikes the rim and decays), and
   **Tangent** (three lobes: two small side lobes swing on slow arcs around the big one's centre,
   the only lobes in the registry with a real `orbit`). Making the mark data rather than a
   component is what let "I like all of them" mean shipping all of them.

3. **The motion moved out of CSS and SMIL into a per-frame clock.** `useMarkClock` counts elapsed
   seconds from the first animation frame and the whole mark is a pure function of that number.
   The old mark could live in SMIL because its motion was a there-and-back interpolation between
   two path snapshots; a travelling wave whose amplitude decays (Hunch) is not expressible that
   way, and a cluster whose lobes each swing on their own period (Tangent) even less so. Reduced
   motion is then exact: the hook **schedules no frames at all** and returns a fixed pose, so the
   mark is really static rather than animating at 0.001 ms.

4. **The bubble replaces the rings everywhere the rings appeared**, the orb and the panel's empty
   state, and the eight-hue gradient is unchanged. The identity was always the palette, not the
   silhouette, which is why the shape could be replaced without the overlay looking like a
   different product.

5. **The way to the styles is the mark itself.** Clicking the empty state's mark opens the
   console's appearance tab ([ADR-0035](ADR-0035-console-and-motion.md) decision 1), where every
   style is drawn live as a tile; choosing one applies it to the orb and the empty state at once.
   A fifth header button was rejected: a mark-shaped button in the resting header would put the
   accent palette on resting chrome, which §1 of the design doc forbids.

6. **The chosen style persists in the brain's preference record**, under the key `overlay.mark`
   ([ADR-0032](ADR-0032-preference-record.md)), beside the theme and the window edge, so it
   outlives a restart and a reinstall of the body.

7. **The labels are movements of thought, and naming is designed as a system.** The mark exists to
   say "still thinking", so its styles are ways a mind moves, and each label names the motion it
   stands for: Mull turns the outline over without settling, Muse keeps a calm surface over a
   drifting film, Hunch is the sudden ripple that strikes the rim and fades, Tangent's side lobes
   swing on arcs around the main one without ever leaving it. This is the worked example for every
   selectable family in the repo, which the maintainer made repo policy when he approved this set:
   one word per entry, one metaphor for the whole family, and the family chosen to mean something
   (a chooser for the thinking signal asks "how does it think?"). Related registries use related
   vocabularies rather than sharing words, so no mark name collides with a theme name, a window
   edge name or any other selectable family.

8. **Each storage key is its label in lowercase, and the keys the styles first shipped under
   still resolve.** `MarkStyle.name` is the value the preference record holds: `mull`, `muse`,
   `hunch`, `tangent`. The styles first shipped as Wobble, Sheen, Ping and Foam under the keys
   `wobble`, `sheen`, `ping` and `foam`, and `resolveMark` maps each to the style it became
   (`wobble` to `mull`, `sheen` to `muse`, `ping` to `hunch`, `foam` to `tangent`), so a preference
   written under an old key still selects the style it named while every new write uses the
   current key. The keys were renamed rather than frozen because nothing beyond the maintainer's
   machine held a stored value. The rule that follows is in AGENTS.md: a key is frozen once
   anything beyond the host machine depends on it, and until then a mismatch between key and label
   is fixed, with the old key kept as an alias, while fixing it is still free.

## Consequences

- `mark/bubble.ts` (pure geometry), `mark/marks.ts` (the registry), `mark/useMarkClock.ts` (the
  clock) and `components/BubbleMark.tsx` (the renderer) replaced `components/ring.ts` and
  `components/RingMark.tsx`, along with the `.orb .rings` animation and the `spin` / `huedrift`
  keyframes in `overlay.css`. The style tiles live in `components/AppearanceTab.tsx`.
- The mark re-renders per animation frame while it is on screen, where the rings cost nothing after
  first paint. Measured in the browser on 2026-07-19 (Chromium at 60 Hz, the engine family of the
  WebView2 the Tauri shell renders in, three seconds of frames each): one mark in the empty state,
  five marks at once (the most the overlay then showed), and the orb running the three-lobe style
  all held a median frame equal to the display interval and a worst frame within 1% of it.
- `docs/assets/logo.jpg` is not the overlay mark and is untouched by this ADR.

## Alternatives rejected

- **Shipping one of the four candidates**: the user liked all four, and with the mark as data each
  extra style costs one literal.
- **Freezing the shipped keys under the new labels**: it would have kept a key that no longer
  names its style, to protect stored values that existed on one machine only (decision 8).

## Related

- Code: `body/app/src/mark/`, `components/BubbleMark.tsx`, `components/Orb.tsx`,
  `components/AppearanceTab.tsx`.
- Design: [overlay-ux.md](../design/overlay-ux.md) §4.
- ADRs: [ADR-0032](ADR-0032-preference-record.md) (the preference record),
  [ADR-0035](ADR-0035-console-and-motion.md) (the console), [ADR-0036](ADR-0036-window-edge.md)
  (the window edge, a related registry named under decision 7).

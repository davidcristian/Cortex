# ADR-0031: The bubble mark, and the mark as a picked style

- **Status:** Accepted
- **Date:** 2026-07-19

## Context

The overlay's activity mark (the corner orb while a turn runs, and the panel's empty state) was
the **living rings**: two sine-modulated wavy bands stroked with the eight-hue gradient,
spinning as one under a CSS `spin` + `huedrift` pair while each band's wave depth pulsed on its
own SMIL clock (ADR-0011's 2026-07-03 addendum).

Two things retired it.

1. **It reads as someone else's mark.** Concentric coloured rings turning around a point is close
   enough to a widely shipped assistant identity that the resemblance is the first thing a viewer
   names. For a personal product whose whole visual argument is "this is mine", that is a defect
   in the mark regardless of how it animates.
2. **The maintainer asked for a soap bubble instead**: an actual bubble, not a perfect circle, sheen
   and all, warping along its radius.

Four candidate bubbles were designed and reviewed as running animations at real size. The user
liked all four, which turned a one-of-four pick into the actual decision below.

## Decision

1. **The mark is a soap bubble, and its geometry is sine harmonics of order two or higher.** A
   lobe is a circle whose radius is modulated by a sum of harmonics, `r(θ) = R·(1 + Σ aᵢ·sin(nᵢθ +
   φᵢ(t)))`, each harmonic travelling at its own period. Because every `nᵢ ≥ 2`, the mean of the
   outline over a revolution is exactly the center: **the centroid and the mean radius are fixed by
   construction**, so the design's standing "no breathing scale, no positional drift, the anchor
   holds rock still" rule (ADR-0011's 2026-07-03 addendum) is a property of the maths rather than
   a convention to remember. An `n = 1` term would translate the whole shape; that is the one
   number the tests guard (`marks.test.ts`, "uses only harmonics of order two or higher").

2. **Four styles ship, as a plug-and-play registry, defaulting to Wobble.** `mark/marks.ts` is the
   deliberate twin of `theme/themes.ts`: a `MarkStyle` is a named set of numbers, `MARKS` is the
   registry, `resolveMark(preference)` falls back to the default, and adding a fifth style is a
   literal in that file and no other code change. The four are **Wobble** (two slow modes roll the
   outline; the default), **Sheen** (near circular, the film crawls underneath), **Ping** (still,
   then a ripple runs the rim and decays), and **Foam** (three lobes jostling as one). Making the
   mark data rather than a component is what let "I like all of them" resolve to shipping all of
   them.

3. **The motion moved out of CSS and SMIL into a per-frame clock.** `useMarkClock` counts elapsed
   seconds from the first animation frame and the whole mark is a pure function of that number.
   The old mark could live in SMIL because its motion was a there-and-back interpolation between
   two path snapshots; a travelling wave whose amplitude decays (Ping) is not expressible that
   way, and a cluster whose lobes each swing on their own period (Foam) even less so. Reduced
   motion is then trivially exact: the hook **schedules no frames at all** and returns a fixed
   pose, so the mark is genuinely static rather than animating at 0.001ms.

4. **The bubble replaces the rings everywhere the rings appeared**, the orb and the panel's empty
   state, and the eight-hue gradient carries over unchanged. The identity was always the palette,
   not the silhouette, which is why the shape could be replaced without the overlay looking like a
   different product.

5. **The picker lives on the mark itself.** Clicking the empty state's mark opens the four styles,
   each drawn live at a glanceable size; choosing one applies it to both places at once. The
   alternative, a fifth header button, was rejected twice over: the header is deliberately four
   buttons, and a mark-shaped button in the resting header would put the accent palette on resting
   chrome, which §1 of the design doc forbids. The control sits on the thing it changes.

6. **The chosen style is session state, exactly like the theme.** `App` holds `markPreference`
   beside the theme `preference`; neither survives a restart today. Persisting appearance choices
   is one deferral for both, recorded in `docs/refinements/body-overlay.md`, not a mark-specific
   gap.

## Consequences

- `mark/bubble.ts` (pure geometry), `mark/marks.ts` (the registry), `mark/useMarkClock.ts` (the
  clock), `components/BubbleMark.tsx` (the renderer) and `components/MarkPicker.tsx` are new;
  `components/ring.ts` and `components/RingMark.tsx` are deleted, along with the `.orb .rings`
  animation and the now-unused `spin` / `huedrift` keyframes in `overlay.css`.
- The mark now re-renders per animation frame while it is on screen, which is a real change from a
  mark that cost nothing after first paint. **Measured** in the browser rather than assumed: three
  seconds of frames in each of the empty state (one mark), the picker open (five marks at once,
  the most the overlay can ever show), and the orb running Foam (three lobes) all held a 16.7ms
  median with a 16.8ms worst frame, so nothing came close to missing the budget. Chromium at 60Hz,
  which is the same engine family as the WebView2 the Tauri shell renders in.
- The picker has no click-away close and is discoverable only by clicking the mark. Both are
  recorded as refinements rather than fixed here, because the honest fix for the second is a
  settings surface the overlay does not have yet.
- `docs/assets/logo.jpg` is not the overlay mark and is untouched by this ADR.

## Addendum (2026-07-20): the fourth style is called Orbit

Decision 2 shipped it as **Foam**, on the strength of the cluster silhouette. What actually
separates it from the other three is the motion, and the motion is orbital: it is the only style
whose lobes carry a real `orbit`, the two small ones swinging on slow arcs around the big one's
centre. The tile now reads **Orbit**, with a note that says what swings.

`MarkStyle.name` stays `"foam"`. It is the value written to the preference record (ADR-0032), so
renaming it would not rename anything, it would drop the choice of every user who had picked this
style and hand them the default back on the next start. The label is what the maintainer reads and the
name is what the record holds, and this is the one style where they differ.

## Addendum (2026-07-21): the styles are named as movements of thought

The tiles now read **Mull** (was Wobble), **Muse** (was Sheen), **Hunch** (was Ping) and
**Tangent** (was Orbit). The mark exists to say "still thinking", so its styles are ways a mind
moves, and each label names the motion it fronts: Mull turns the outline over without settling,
Muse keeps a calm surface over a drifting film, Hunch is the sudden ripple that strikes the rim
and fades, Tangent's side lobes swing on arcs around the main one without ever leaving it.

The scheme is the point, not just the words. Naming here is a designed system with the same craft
as the visuals, which the maintainer made standing policy when he approved this set: one word per
style, distinct first letters, one metaphor for the whole family, and the family chosen to mean
something (a picker for the thinking signal should ask "how does it think?"). Sibling registries
speak sibling languages rather than sharing words, so no mark name collides with a theme name or
any other pickable family.

Every `MarkStyle.name` is now a frozen key that differs from its label (`wobble`, `sheen`,
`ping`, `foam`): the reasoning of the 2026-07-20 addendum holds for all four, and its closing
line ("the one style where they differ") is superseded here. Labels, notes and comments changed;
no key, number or behaviour did.

## Addendum (2026-07-21, later): the keys are healed

The maintainer corrected the premise under the two addenda above: the project is private, nothing is
in production, and no machine but his holds a stored preference, so key-freezing is policy that
has not started yet rather than physics. Every `MarkStyle.name` now matches its label (`mull`,
`muse`, `hunch`, `tangent`), and the shipped keys (`wobble`, `sheen`, `ping`, `foam`) live on as
aliases inside `resolveMark`, so a preference written before the healing still resolves to the
style it named while every new write uses the current key. The freeze rule itself moved into
AGENTS.md in its corrected form: keys freeze once anything beyond the host machine depends on
them, and until then a mismatch is healed while healing is free.

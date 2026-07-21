// The overlay's activity mark, as a plug-and-play registry (the same shape as theme/themes.ts):
// a mark style is a named set of bubble parameters, and adding one to MARKS makes it pickable
// with no other code change. Four ship (design/overlay-ux.md §4, ADR-0031); the user picks one
// from the empty state and Mull is the default. All geometry lives in bubble.ts; this file is
// only the numbers.
//
// The labels are movements of thought: the mark is the overlay's thinking signal, so the picker
// asks "how does it think?" and each label answers with how that style moves (ADR-0031 addendum).
// `name` is the frozen storage key a style first shipped under, the value the preference record
// holds, so every key now differs from its label; the note on Tangent says why none may change.

import type { Envelope, Harmonic, Lobe, Orbit } from "./bubble";

/** A lobe that does not swing: the orbit anchor is its own center, so the rotation is identity. */
function pinned(cx: number, cy: number): Orbit {
  return { cx, cy, degrees: 0, periodSeconds: 1 };
}

function wave(
  waves: number,
  amplitude: number,
  periodSeconds: number,
  direction: 1 | -1,
  envelope: Envelope,
): Harmonic {
  return { waves, amplitude, periodSeconds, direction, envelope };
}

/** The parameters that make one bubble style. The film is the eight-hue palette, stroked thickly
 *  just inside the rim (where a real film thins and colors) and rotated; the inner band is a
 *  second, slower, opposed pass that keeps the interior from looking flat. */
export interface MarkStyle {
  readonly name: string;
  /** How the style is named in the picker. */
  readonly label: string;
  /** One-line description of what moves, shown under the picker. */
  readonly note: string;
  readonly filmPeriodSeconds: number;
  readonly innerFilmPeriodSeconds: number;
  readonly innerFilmOpacity: number;
  /** Steady film, or one that brightens with each crest (Hunch). */
  readonly filmEnvelope: Envelope;
  readonly lobes: readonly Lobe[];
}

/** Turning it over: two slow modes roll the outline around and it never settles on a shape. */
export const MULL: MarkStyle = {
  name: "wobble",
  label: "Mull",
  note: "Two slow modes turn the outline over, never settling",
  filmPeriodSeconds: 26,
  innerFilmPeriodSeconds: 40,
  innerFilmOpacity: 0.25,
  filmEnvelope: "steady",
  lobes: [
    {
      cx: 50,
      cy: 50,
      r: 38,
      orbit: pinned(50, 50),
      harmonics: [
        wave(2, 0.055, 11, 1, "steady"),
        wave(3, 0.032, 8, -1, "steady"),
        wave(5, 0.011, 6, 1, "steady"),
      ],
    },
  ],
};

/** Composed outside, alive inside: two opposed interference bands crawl across the film. */
export const MUSE: MarkStyle = {
  name: "sheen",
  label: "Muse",
  note: "The outline keeps its calm; the film drifts beneath it",
  filmPeriodSeconds: 15,
  innerFilmPeriodSeconds: 24,
  innerFilmOpacity: 0.55,
  filmEnvelope: "steady",
  lobes: [
    {
      cx: 50,
      cy: 50,
      r: 39,
      orbit: pinned(50, 50),
      harmonics: [wave(2, 0.02, 14, 1, "steady"), wave(3, 0.012, 10, -1, "steady")],
    },
  ],
};

/** Mostly still, then a ripple runs the rim and decays, the way a film answers a nudge. */
export const HUNCH: MarkStyle = {
  name: "ping",
  label: "Hunch",
  note: "A ripple strikes the rim every few seconds, then fades",
  filmPeriodSeconds: 30,
  innerFilmPeriodSeconds: 44,
  innerFilmOpacity: 0.25,
  filmEnvelope: "ping",
  lobes: [
    {
      cx: 50,
      cy: 50,
      r: 38,
      orbit: pinned(50, 50),
      harmonics: [wave(6, 0.032, 2.6, 1, "ping"), wave(2, 0.018, 12, 1, "steady")],
    },
  ],
};

/** A cluster: two small lobes surface behind the big one, off axis so it never reads as a face.
 *  Smallest first, so the big bubble draws over them and they read as clustered, not stuck on.
 *
 *  The two small ones are the only lobes in the registry that swing: each carries a real `orbit`
 *  around the big lobe's centre, side thoughts on arcs that never leave the main one, which is
 *  what the label names. `name` stays "foam", the label this first shipped under, because it is
 *  the value written to the preference record: change it and every user who picked this style
 *  silently falls back to the default. */
export const TANGENT: MarkStyle = {
  name: "foam",
  label: "Tangent",
  note: "Two side thoughts swing on slow arcs around the main one",
  filmPeriodSeconds: 28,
  innerFilmPeriodSeconds: 40,
  innerFilmOpacity: 0.25,
  filmEnvelope: "steady",
  lobes: [
    {
      cx: 66,
      cy: 23,
      r: 9.5,
      orbit: { cx: 45, cy: 52, degrees: 7, periodSeconds: 11 },
      harmonics: [wave(2, 0.06, 6, -1, "steady"), wave(3, 0.035, 4.2, 1, "steady")],
    },
    {
      cx: 74,
      cy: 70,
      r: 16,
      orbit: { cx: 45, cy: 52, degrees: 8, periodSeconds: 9 },
      harmonics: [wave(2, 0.05, 7, 1, "steady"), wave(3, 0.03, 5, -1, "steady")],
    },
    {
      cx: 45,
      cy: 52,
      r: 30,
      orbit: pinned(45, 52),
      harmonics: [wave(2, 0.042, 12, 1, "steady"), wave(3, 0.024, 9, -1, "steady")],
    },
  ],
};

/** The registry is plug-and-play: add a `MarkStyle` here and it becomes pickable. */
export const MARKS: readonly MarkStyle[] = [MULL, MUSE, HUNCH, TANGENT];

/** Resolve the active mark: a known name wins, anything else falls back to the default. */
export function resolveMark(preference: string | null): MarkStyle {
  if (preference !== null) {
    const chosen = MARKS.find((mark) => mark.name === preference);
    if (chosen !== undefined) {
      return chosen;
    }
  }
  return MULL;
}

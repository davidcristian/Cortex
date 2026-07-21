// The overlay's activity mark, as a registry: a style is a named set of bubble parameters, and
// adding one to `MARKS` makes it selectable. The geometry is in `bubble.ts`; this file is only the
// numbers. `name` is the key the stored preference holds.

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
 *  just inside the rim and rotated; the inner band is a second, slower, opposite pass. */
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
  name: "mull",
  label: "Mull",
  note: "Two slow modes roll the outline over, settling on nothing",
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
  name: "muse",
  label: "Muse",
  note: "A surface holding its calm, with the film adrift far beneath it",
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
  name: "hunch",
  label: "Hunch",
  note: "Still, until an idea strikes the rim and rings away",
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

/** A cluster: two small lobes sit behind the big one, off axis so it never reads as a face, and
 *  smallest first so the big one draws over them. They are the only lobes here that swing. */
export const TANGENT: MarkStyle = {
  name: "tangent",
  label: "Tangent",
  note: "Two side thoughts circling the one in the middle, never leaving it",
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

/** The keys the four styles first shipped under, still resolved so a preference stored before
 *  the rename reaches the style it named. New writes always use the current keys. */
const LEGACY_NAMES: Record<string, string> = {
  wobble: "mull",
  sheen: "muse",
  ping: "hunch",
  foam: "tangent",
};

/** Resolve the active mark: a known name is used as is, an old name resolves to what it became,
 *  and anything else falls back to the default. */
export function resolveMark(preference: string | null): MarkStyle {
  if (preference !== null) {
    const name = LEGACY_NAMES[preference] ?? preference;
    const chosen = MARKS.find((mark) => mark.name === name);
    if (chosen !== undefined) {
      return chosen;
    }
  }
  return MULL;
}
